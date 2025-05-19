/**
 * Returns the point between the source point and the destination point at
 * the percentage part of the segment connecting them.
 * 
 * Example:
 * interpolate((0,0), (0,1), 0.25) --> (0,0.25)
 * 
 * @param {point} Source Point
 * @param {point} Destination Point
 * @param {float (in range [0, 1])} Percentage travelled 
 * @returns {point}
 */
function interpolatePosition(p1, p2, prog) {
    return [p1[0] + prog * (p2[0] - p1[0]), p1[1] + prog * (p2[1] - p1[1])]
}

/**
 * Computes the euclidean distance between two points.
 * 
 * @param {point} Point 1 
 * @param {point} Point 2
 * @returns {float} Euclidean Distance
 */
function getEuclideanDistance(p1, p2) {
    return Math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2);
}

function roundPlaces(x, places) {
    return Math.round(x * (10**places)) / (10**places);
}

const REFRESH_TIME = 16.67;  // 60 FPS for smoother animation
// Make GLOBAL_TIME_MS available globally
window.GLOBAL_TIME_MS = window.GLOBAL_TIME_MS || 0;

// Global Maps for storing different types of markers
window.appearMarkers = new Map();  // Store passenger appear markers
window.loadMarkers = new Map();    // Store load markers
window.dropoffMarkers = new Map(); // Store dropoff markers
window.enqueueLines = new Map();   // Store lines connecting trikes to enqueued passengers
// Format: Map<passengerId, {trikeId: string, line: L.Polyline}>

// Global frame counter
window.CURRENT_FRAME = 0;

function update_time() {
    window.GLOBAL_TIME_MS += REFRESH_TIME;
    setTimeout(update_time, REFRESH_TIME);
}

// Start the time update loop
update_time();

L.Marker.MovingMarker = L.Marker.extend({

    statics: {
        notStartedState: 0,
        runningState: 1,
        pausedState: 2,
        endedState: 3
    },

    initialize: function (id, path, stime, dtime, speed, events) {
        console.log(`Initializing marker ${id} with path:`, path);
        this.id = id;
        this.SPEED = speed;
        this.path = path;
        this.stime = stime;
        this.dtime = dtime;
        this.events = events;
        this.eventMarkers = []; // Store references to event markers
        this.passengers = new Set(); // Track current passengers
        this.currentPathIndex = 0;
        this.currentEventIndex = 0;

        // Only create and add the base marker for tricycles
        if (!this.id.startsWith("passenger")) {
            // Create a hollow circle marker for tricycles
            const markerIcon = L.divIcon({
                className: 'trike-marker',
                html: `<div style="
                    width: 12px;
                    height: 12px;
                    border-radius: 50%;
                    border: 4px solid #0000FF;
                    background-color: transparent;
                "></div>`
            });

            if (this.events == null) {
                console.log(`Creating base marker for ${this.id} at path[0]:`, path[0]);
                L.Marker.prototype.initialize.call(this, path[0], { icon: markerIcon });
                this.setLatLng(path[0]);
            } else {
                console.log(`Creating base marker for ${this.id} at [0,0]`);
                L.Marker.prototype.initialize.call(this, [0,0], { icon: markerIcon });
                this.setLatLng([0,0]);
            }
            console.log(`Adding marker ${this.id} to map`);
            this.addTo(map);

            // add the tooltip with initial passenger state
            this.updateTooltip();
        }
        
        // simulation specific
        this.simulationState = L.Marker.MovingMarker.notStartedState;
        this._animId = 0; 
        this._startTimeStamp = 0;
        this._prevTimeStamp = 0;
        this._animRequested = false;

        // sample specific
        this._currentPathIndex = 0;
        this._currentEventIndex = 0;
    },

    isRunning: function() {
        return this.simulationState === L.Marker.MovingMarker.runningState;
    },

    start: function() {
        this._startAnimation();
    },

    onAdd: function (map) {
        L.Marker.prototype.onAdd.call(this, map);

        if (this.isRunning()) {
            this._resumeAnimation();
        }
    },

    onRemove: function(map) {
        L.Marker.prototype.onRemove.call(this, map);
        this._stopAnimation();
    },

    _startAnimation: function() {
        this.simulationState = L.Marker.MovingMarker.runningState;
        this._animId = L.Util.requestAnimFrame(function(_timestamp) {
            const timestamp = GLOBAL_TIME_MS;
            this._startTimeStamp = timestamp;
            this._prevTimeStamp = timestamp;
            this._animate(timestamp);
        }, this, true);
        this._animRequested = true;
    },

    _resumeAnimation: function() {
        if (!this._animRequested) {
            this._animRequested = true;
            this._animId = L.Util.requestAnimFrame(function(_timestamp) {
                const timestamp = GLOBAL_TIME_MS;
                this._animate(timestamp);
            }, this, true);
        }
    },

    _stopAnimation: function() {
        if (this._animRequested) {
            L.Util.cancelAnimFrame(this._animId);
            this._animRequested = false;
        }
    },

    // Add new method to create event markers
    createEventMarker: function(lat, lng, message) {
        // Skip creating markers for enqueue events and trike appear events
        if (message.includes("ENQUEUE") || (message.includes("APPEAR") && this.id.startsWith("trike"))) {
            return null;
        }

        const key = `${lat.toFixed(6)},${lng.toFixed(6)}`;
        if (!window.tooltipStackCounter) window.tooltipStackCounter = {};
        if (!window.tooltipStackCounter[key]) window.tooltipStackCounter[key] = 0;
        const offset = window.tooltipStackCounter[key] * 24; // 24px per stacked tooltip
        window.tooltipStackCounter[key] += 1;

        // Determine marker color based on event type
        const isLoad = message.includes("LOAD");
        const isDropoff = message.includes("DROP-OFF");
        const isPassengerAppear = message.includes("APPEAR") && this.id.startsWith("passenger");
        const isTrikeAppear = message.includes("APPEAR") && this.id.startsWith("trike");
        const isEnqueue = message.includes("ENQUEUE") && this.id.startsWith("passenger");
        const isReset = message.includes("RESET") && this.id.startsWith("passenger");

        console.log(`Creating marker for ${message} - isEnqueue: ${isEnqueue}, isReset: ${isReset}`);

        let markerColor;
        if (isPassengerAppear) {
            markerColor = 'red';
        } else if (isTrikeAppear) {
            markerColor = 'blue';
        } else if (isEnqueue) {
            markerColor = 'orange';
        } else if (isReset) {
            markerColor = 'red';
        } else if (isLoad) {
            markerColor = 'orange';
        } else if (isDropoff) {
            markerColor = 'green';
        } else {
            markerColor = 'gray';
        }
        
        const marker = L.marker([lat, lng], {
            icon: L.divIcon({
                className: 'event-marker',
                html: `<div style="background-color: ${markerColor}; width: 8px; height: 8px; border-radius: 50%;"></div>`,
                iconSize: [8, 8],
                iconAnchor: [4, 4]  // Center the icon
            })
        })
        .addTo(map)
        .bindTooltip(message, {
            permanent: false, // Only show on hover
            direction: 'top',
            className: 'event-tooltip-stacked',
            offset: [0, -offset]
        });
        
        this.eventMarkers.push(marker);

        // Store markers in appropriate global Maps
        if (isPassengerAppear) {
            const passengerId = this.id;
            console.log(`Storing appear marker for ${passengerId}`);
            window.appearMarkers.set(passengerId, marker);
        } else if (isLoad) {
            const match = message.match(/passenger_\d+/);
            if (match) {
                const passengerId = match[0];
                console.log(`Storing load marker for ${passengerId}`);
                window.loadMarkers.set(passengerId, marker);
            } else {
                console.warn(`Could not extract passenger ID from message: ${message}`);
            }
        } else if (isDropoff) {
            const match = message.match(/passenger_\d+/);
            if (match) {
                const passengerId = match[0];
                console.log(`Storing dropoff marker for ${passengerId}`);
                window.dropoffMarkers.set(passengerId, marker);
            } else {
                console.warn(`Could not extract passenger ID from message: ${message}`);
            }
        }

        return marker;
    },

    // Add method to log events
    logEvent: function(time, type, data) {
        const eventLog = document.getElementById('eventLog');
        const entry = document.createElement('div');
        entry.className = 'event-log-entry';
        
        // Format the event message
        let message = `Frame ${time}: ${this.id} ${type}`;
        if (data) {
            message += ` ${data}`;
        }
        
        entry.textContent = message;
        eventLog.appendChild(entry);
        eventLog.scrollTop = eventLog.scrollHeight;
    },

    // Add method to update tooltip with current passenger list
    updateTooltip: function() {
        const passengerList = Array.from(this.passengers).sort((a, b) => {
            // Extract numbers from passenger IDs for proper sorting
            const numA = parseInt(a.split('_')[1]);
            const numB = parseInt(b.split('_')[1]);
            return numA - numB;
        }).join(' ');
        this.unbindTooltip();
        this.bindTooltip(`${this.id}: ${passengerList}`, {
            permanent: false,
            direction: 'top'
        });
    },

    // Add method to update marker color based on status
    updateMarkerColor: function(status) {
        if (this.id.startsWith("passenger")) return; // Only update tricycle markers

        let color;
        switch(status) {
            case 0: // IDLE
            case 3: // ROAMING
            case 4: // RETURNING
            case 2: // TERMINAL
                color = 'blue'; // Blue
                break;
            case 1: // SERVING
                color = 'orange'; // Orange
                break;
            case 5: // ENQUEUING
                color = 'red'; // Red
                break;
            default:
                color = 'blue'; // Default to blue
        }

        const markerIcon = L.divIcon({
            className: 'trike-marker',
            html: `<div style="
                width: 12px;
                height: 12px;
                border-radius: 50%;
                border: 4px solid ${color};
                background-color: transparent;
            "></div>`
        });

        this.setIcon(markerIcon);
    },

    // Add method to create roam path visualization
    createRoamPath: function(path) {
        // Remove any existing roam path for this trike
        if (this.roamPath) {
            this.roamPath.line.remove();
            this.roamPath.startMarker.remove();
            this.roamPath.endMarker.remove();
        }

        // Create start and end markers
        const startMarker = L.marker(path[0], {
            icon: L.divIcon({
                className: 'roam-endpoint-marker',
                html: `<div style="background-color: blue; width: 8px; height: 8px;"></div>`,
                iconSize: [8, 8],
                iconAnchor: [4, 4]
            })
        }).addTo(map);

        const endMarker = L.marker(path[path.length - 1], {
            icon: L.divIcon({
                className: 'roam-endpoint-marker',
                html: `<div style="background-color: blue; width: 8px; height: 8px;"></div>`,
                iconSize: [8, 8],
                iconAnchor: [4, 4]
            })
        }).addTo(map);

        // Create the path line
        const line = L.polyline(path, {
            color: 'blue',
            weight: 2,
            opacity: 0.25
        }).addTo(map);

        // Store the roam path elements
        this.roamPath = {
            line: line,
            startMarker: startMarker,
            endMarker: endMarker
        };
    },

    _animate: function(_timestamp, noRequestAnim) {
        this._animRequested = false;
        const timestamp = GLOBAL_TIME_MS;

        if (this.stime + this._startTimeStamp <= timestamp) {
            const continueAnim = (this.dtime + this._startTimeStamp) >= timestamp;
            
            if (!continueAnim) {
                console.log(timestamp-this._startTimeStamp, "stopping", this.id);
                this.setLatLng([0,0]);
                this._stopAnimation();
                return;
            }
            
            if (this.events != null) {
                const curEvent = this.events[this.currentEventIndex];
                if (curEvent.type == "APPEAR") {
                    // For passengers, use the event location directly
                    const location = this.id.startsWith("passenger") ? 
                        [curEvent.location[1], curEvent.location[0]] : // Convert [x,y] to [lat,lng]
                        this.path[0];
                    this.setLatLng(location);
                    this.updateTooltip();
                    // Create event marker for APPEAR
                    const message = `${this.id}: ${curEvent.type}`;
                    this.createEventMarker(location[0], location[1], message);
                    this.logEvent(Math.floor((timestamp - this._startTimeStamp) / REFRESH_TIME), curEvent.type);
                    this.currentEventIndex += 1;
                } else if (curEvent.type == "MOVE") {
                    const timeElapsed = timestamp - this._prevTimeStamp;
                    const pathDistanceTravelled = this.SPEED * timeElapsed;
                    const curPoint = this.path[this.currentPathIndex];
                    const nxtPoint = this.path[this.currentPathIndex+1];
                    const segmentProgress = Math.min(1, pathDistanceTravelled / getEuclideanDistance(curPoint, nxtPoint));
                    const new_position = interpolatePosition(curPoint, nxtPoint, segmentProgress);
            
                    this.setLatLng(new_position);

                    // Update enqueue lines if this is a trike
                    if (this.id.startsWith("trike")) {
                        this.updateEnqueueLines();
                    }

                    if (Math.round(segmentProgress*100) == 100) {
                        this._prevTimeStamp = timestamp;
                        this.currentPathIndex += 1;
                        curEvent.data -= 1;

                        if (curEvent.data == 0) {
                            this.currentEventIndex += 1;
                            // If this was a roam path, create the visualization
                            if (curEvent.isRoam && this.currentPathIndex > 0) {
                                const startIdx = Math.max(0, this.currentPathIndex - curEvent.pathLength);
                                const endIdx = Math.min(this.path.length - 1, this.currentPathIndex);
                                if (startIdx < endIdx) {
                                    const roamPath = this.path.slice(startIdx, endIdx + 1);
                                    if (roamPath.length >= 2) {
                                        this.createRoamPath(roamPath);
                                    }
                                }
                            }
                        }
                    }
                } else if (curEvent.type == "DROP-OFF" || curEvent.type == "LOAD" || 
                          curEvent.type == "ENQUEUE" || curEvent.type == "RESET") {
                    // Store current position and ensure it's maintained
                    const eventPoint = this.path[this.currentPathIndex];
                    if (eventPoint && Array.isArray(eventPoint) && eventPoint.length === 2) {
                        // Ensure we're at the exact event location
                        this.setLatLng(eventPoint);
                        
                        const message = `${this.id}: ${curEvent.type} ${curEvent.data || ""}`;
                        const eventMarker = this.createEventMarker(eventPoint[0], eventPoint[1], message);
                        
                        // Log the event with the actual time from the event object
                        this.logEvent(curEvent.time, curEvent.type, curEvent.data);
                        console.log(`Processing ${curEvent.type} event at time ${curEvent.time} for ${this.id}`);
                        
                        // Update passenger set for tricycles and passenger states
                        if (this.id.startsWith("trike")) {
                            if (curEvent.type == "DROP-OFF") {
                                this.passengers.delete(curEvent.data);
                                updatePassengerState(curEvent.data, "COMPLETED");
                                // Update marker color based on new status
                                this.updateMarkerColor(4); // RETURNING
                                // Remove the load marker for this passenger with a small delay
                                const loadMarker = window.loadMarkers.get(curEvent.data);
                                if (loadMarker) {
                                    setTimeout(() => {
                                        loadMarker.remove();
                                        window.loadMarkers.delete(curEvent.data);
                                    }, 100); // Small delay to prevent visual jarring
                                }
                            } else if (curEvent.type == "LOAD") {
                                // Batch all updates for LOAD event
                                const passengerId = curEvent.data;
                                
                                // Update passenger state
                                updatePassengerState(passengerId, "ONBOARD");
                                
                                // Update marker color before adding passenger
                                this.updateMarkerColor(1); // SERVING
                                
                                // Add passenger to set
                                this.passengers.add(passengerId);
                                
                                // Remove the appear marker with a small delay
                                const appearMarker = window.appearMarkers.get(passengerId);
                                if (appearMarker) {
                                    setTimeout(() => {
                                        appearMarker.remove();
                                        window.appearMarkers.delete(passengerId);
                                    }, 100);
                                }
                                
                                // Remove the enqueue line with a small delay
                                const lineData = window.enqueueLines.get(passengerId);
                                if (lineData && lineData.trikeId === this.id) {
                                    setTimeout(() => {
                                        lineData.line.remove();
                                        window.enqueueLines.delete(passengerId);
                                    }, 100);
                                }
                                
                                // Update tooltip after all changes
                                this.updateTooltip();
                            } else if (curEvent.type == "ENQUEUE") {
                                // Update passenger state when tricycle enqueues a passenger
                                updatePassengerState(curEvent.data, "ENQUEUED");
                                // Update marker color based on new status
                                this.updateMarkerColor(5); // ENQUEUING
                                // Create a line connecting the trike to the passenger
                                const passengerMarker = window.appearMarkers.get(curEvent.data);
                                if (passengerMarker) {
                                    const line = L.polyline([
                                        this.getLatLng(),
                                        passengerMarker.getLatLng()
                                    ], {
                                        color: 'red',
                                        weight: 2,
                                        opacity: 1,
                                        dashArray: '5, 10'
                                    }).addTo(map);
                                    
                                    window.enqueueLines.set(curEvent.data, {
                                        trikeId: this.id,
                                        line: line
                                    });
                                }
                                this.updateTooltip();
                            }
                        } else if (this.id.startsWith("passenger")) {
                            // Handle passenger-specific events
                            if (curEvent.type === "ENQUEUE") {
                                updatePassengerState(this.id, "ENQUEUED");
                                console.log(`Passenger ${this.id} enqueued by ${curEvent.data}`);
                            } else if (curEvent.type === "RESET") {
                                updatePassengerState(this.id, "WAITING");
                                console.log(`Passenger ${this.id} reset by ${curEvent.data}`);
                            }
                        }
                    } else {
                        console.warn(`Invalid event point for ${this.id}:`, eventPoint);
                    }
                    
                    // Update timestamps to maintain position
                    this._prevTimeStamp = timestamp;
                    this.currentEventIndex += 1;
                } else if (curEvent.type == "WAIT") {
                    const timeElapsed = timestamp - this._prevTimeStamp;
                    curEvent.data -= timeElapsed;
                    if (curEvent.data <= 0) {
                        this.currentEventIndex += 1;
                    }
                } else if (curEvent.type == "FINISH") {
                    this.unbindTooltip();
                    this.bindTooltip(`${this.id}: Finished trips`, {
                        permanent: false,
                        direction: 'top'
                    });
                    console.log(timestamp-this._startTimeStamp, this.id, ": Done");
                    noRequestAnim = true;
                } else {
                    console.error(`Unknown event type: ${curEvent.type}`, curEvent);
                    this.currentEventIndex += 1;
                }
            }
        } else {
            this._prevTimeStamp = timestamp;
        }
        
        if (!noRequestAnim) {
            this._animId = L.Util.requestAnimFrame(this._animate, this, false);
            this._animRequested = true;
        }
    },

    setSimTime: function(simTime) {
        // Calculate where the marker should be at simTime
        // This logic should mimic what _animate does, but for a specific time
        // You may need to store the start time and speed as properties

        // Example logic (you may need to adapt this to your plugin's structure):
        let elapsed = simTime - this.stime;
        if (elapsed < 0) elapsed = 0;

        // Find which segment of the path we're on
        let totalDist = 0;
        let segmentIndex = 0;
        let segmentProgress = 0;
        let found = false;

        for (let i = 0; i < this.path.length - 1; i++) {
            let segDist = getEuclideanDistance(this.path[i], this.path[i+1]);
            let segTime = segDist / this.SPEED;
            if (elapsed < segTime) {
                segmentIndex = i;
                segmentProgress = elapsed / segTime;
                found = true;
                break;
            }
            elapsed -= segTime;
        }
        if (!found) {
            // At the end of the path
            segmentIndex = this.path.length - 2;
            segmentProgress = 1;
        }

        let curPoint = this.path[segmentIndex];
        let nxtPoint = this.path[segmentIndex + 1];
        let new_position = interpolatePosition(curPoint, nxtPoint, segmentProgress);

        this.setLatLng(new_position);
    },

    // Update the updateEnqueueLines method
    updateEnqueueLines: function() {
        // Update all enqueue lines for this trike
        window.enqueueLines.forEach((lineData, passengerId) => {
            if (lineData.trikeId === this.id) {
                const passengerMarker = window.appearMarkers.get(passengerId);
                if (passengerMarker) {
                    lineData.line.setLatLngs([
                        this.getLatLng(),
                        passengerMarker.getLatLng()
                    ]);
                }
            }
        });
    },

    // Update remove method to clean up lines and roam path
    remove: function() {
        // Remove all event markers
        this.eventMarkers.forEach(marker => marker.remove());
        this.eventMarkers = [];
        
        // Remove roam path if it exists
        if (this.roamPath) {
            this.roamPath.line.remove();
            this.roamPath.startMarker.remove();
            this.roamPath.endMarker.remove();
        }
        
        // Remove all enqueue lines for this trike
        if (this.id.startsWith("trike")) {
            window.enqueueLines.forEach((lineData, passengerId) => {
                if (lineData.trikeId === this.id) {
                    lineData.line.remove();
                    window.enqueueLines.delete(passengerId);
                }
            });
        }
        
        // Call parent remove
        L.Marker.prototype.remove.call(this);
    }
});

L.Marker.movingMarker = function (id, path, stime=0, dtime=Infinity, speed=0.0000005, events=null) {
    // Speed is already scaled from map.js, just use it directly
    console.log(`Creating marker ${id} with speed ${speed} degrees/ms`);
    return new L.Marker.MovingMarker(id, path, stime, dtime, speed, events);
}