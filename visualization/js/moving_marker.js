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
let GLOBAL_TIME_MS = 0;

function update_time() {
    GLOBAL_TIME_MS += REFRESH_TIME;
    setTimeout(update_time, REFRESH_TIME);
}

update_time()

L.Marker.MovingMarker = L.Marker.extend({

    statics: {
        notStartedState: 0,
        runningState: 1,
        pausedState: 2,
        endedState: 3
    },

    initialize: function (id, path, stime, dtime, speed, events) {
        this.id = id;
        this.SPEED = speed;
        this.path = path;
        this.stime = stime;
        this.dtime = dtime;
        this.events = events;
        this.eventMarkers = []; // Store references to event markers
        this.passengers = new Set(); // Track current passengers

        // Only create and add the base marker for tricycles
        if (!this.id.startsWith("passenger")) {
            if (this.events == null) {
                L.Marker.prototype.initialize.call(this, path[0]);
                this.setLatLng(path[0]);
                console.log(this.id, "setting to", path[0]);
            } else {
                L.Marker.prototype.initialize.call(this, [0,0]);
                this.setLatLng([0,0]);
                console.log(this.id, "setting to", [0,0]);
            }
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
        const isEnqueue = message.includes("ENQUEUE");
        const isReset = message.includes("RESET");

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
            markerColor = 'yellow';
        } else if (isDropoff) {
            markerColor = 'green';
        } else {
            markerColor = 'gray';
        }
        
        const marker = L.marker([lat, lng], {
            icon: L.divIcon({
                className: 'event-marker',
                html: `<div style="background-color: ${markerColor}; width: 8px; height: 8px; border-radius: 50%;"></div>`
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
        return marker;
    },

    // Add method to log events
    logEvent: function(time, type, data) {
        const eventLog = document.getElementById('eventLog');
        const entry = document.createElement('div');
        entry.className = 'event-log-entry';
        entry.textContent = `Frame ${time}: ${this.id} ${type} ${data ?? ""}`;
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
        this.bindTooltip(`${this.id}: ${passengerList}`).openTooltip();
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
                const curEvent = this.events[this._currentEventIndex];
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
                    this._currentEventIndex += 1;
                } else if (curEvent.type == "MOVE") {
                    const timeElapsed = timestamp - this._prevTimeStamp;
                    const pathDistanceTravelled = this.SPEED * timeElapsed;
                    const curPoint = this.path[this._currentPathIndex];
                    const nxtPoint = this.path[this._currentPathIndex+1];
                    const segmentProgress = Math.min(1, pathDistanceTravelled / getEuclideanDistance(curPoint, nxtPoint));
                    const new_position = interpolatePosition(curPoint, nxtPoint, segmentProgress);
            
                    this.setLatLng(new_position);

                    if (Math.round(segmentProgress*100) == 100) {
                        this._prevTimeStamp = timestamp;
                        this._currentPathIndex += 1;
                        curEvent.data -= 1;

                        if (curEvent.data == 0) {
                            this._currentEventIndex += 1;
                        }
                    }
                } else if (curEvent.type == "DROP-OFF" || curEvent.type == "LOAD" || 
                          curEvent.type == "ENQUEUE" || curEvent.type == "RESET") {
                    // Store current position and ensure it's maintained
                    const eventPoint = this.path[this._currentPathIndex];
                    this.setLatLng(eventPoint);
                    
                    const message = `${this.id}: ${curEvent.type} ${curEvent.data || ""}`;
                    this.createEventMarker(eventPoint[0], eventPoint[1], message);
                    this.logEvent(Math.floor((timestamp - this._startTimeStamp) / REFRESH_TIME), curEvent.type, curEvent.data);
                    console.log(timestamp-this._startTimeStamp, message);
                    
                    // Update passenger set for tricycles
                    if (this.id.startsWith("trike")) {
                        if (curEvent.type == "DROP-OFF") {
                            this.passengers.delete(curEvent.data);
                        } else if (curEvent.type == "LOAD") {
                            this.passengers.add(curEvent.data);
                        }
                        this.updateTooltip();
                    }
                    
                    // Update timestamps to maintain position
                    this._prevTimeStamp = timestamp;
                    this._currentEventIndex += 1;
                } else if (curEvent.type == "WAIT") {
                    const timeElapsed = timestamp - this._prevTimeStamp;
                    curEvent.data -= timeElapsed;
                    if (curEvent.data <= 0) {
                        this._currentEventIndex += 1;
                    }
                } else if (curEvent.type == "FINISH") {
                    this.unbindTooltip();
                    this.bindTooltip(`${this.id}: Finished trips`).openTooltip();
                    console.log(timestamp-this._startTimeStamp, this.id, ": Done");
                    noRequestAnim = true;
                }
                else {
                    console.error(`Unknown event: ${curEvent}`)
                    this._currentEventIndex += 1;
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

    // Add cleanup method
    remove: function() {
        // Remove all event markers
        this.eventMarkers.forEach(marker => marker.remove());
        this.eventMarkers = [];
        // Call parent remove
        L.Marker.prototype.remove.call(this);
    }
});

L.Marker.movingMarker = function (id, path, stime=0, dtime=Infinity, speed=0.0000005, events=null) {
    // Speed is already scaled from map.js, just use it directly
    console.log(`Creating marker ${id} with speed ${speed} degrees/ms`);
    return new L.Marker.MovingMarker(id, path, stime, dtime, speed, events);
}