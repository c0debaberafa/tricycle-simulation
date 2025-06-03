/**
 * State and Visual Management Module
 * 
 * This module handles:
 * - State management for passengers and trikes
 * - Visual updates and marker management
 */

import { isValidCoordinates } from './config.js';

// Global configuration
const REFRESH_TIME = 100; // Time between frames in milliseconds

// ===== State Management =====
export class StateManager {
    constructor(visualManager) {
        this.visualManager = visualManager;
        this.passengerStates = {
            WAITING: new Set(),
            ENQUEUED: new Set(),
            ONBOARD: new Set(),
            COMPLETED: new Set()
        };

        this.tricycleStates = {
            DEFAULT: new Set(),
            ENQUEUEING: new Set(),
            SERVING: new Set()
        };

        this.maxPathIndex = 0;
    }

    updatePassengerState(passengerId, newState) {
        // Remove from all states
        Object.values(this.passengerStates).forEach(set => set.delete(passengerId));
        // Add to new state
        this.passengerStates[newState].add(passengerId);
    }

    getPassengerState(passengerId) {
        for (const [state, passengers] of Object.entries(this.passengerStates)) {
            if (passengers.has(passengerId)) {
                return state;
            }
        }
        return null;
    }

    reset() {
        // Reset all states
        Object.keys(this.passengerStates).forEach(key => {
            this.passengerStates[key].clear();
        });
        // Reset tricycle states
        Object.keys(this.tricycleStates).forEach(key => {
            this.tricycleStates[key].clear();
        });
        this.maxPathIndex = 0;  // Reset max path index
    }

    // Add method to track trike passengers
    updateTrikePassengers(trikeId, passengers) {
        // Remove from all states first
        Object.keys(this.tricycleStates).forEach(key => {
            this.tricycleStates[key].delete(trikeId);
        });
        
        // Add to appropriate state based on passengers
        if (passengers && passengers.size > 0) {
            this.tricycleStates.SERVING.add(trikeId);
        } else {
            this.tricycleStates.DEFAULT.add(trikeId);
        }
    }

    getTrikePassengers(trikeId) {
        return this.tricycleStates.get(trikeId) || new Set();
    }

    // Add method to validate event
    isValidEvent(event) {
        return event && 
               event.type && 
               event.time !== undefined && 
               (!event.data || isValidCoordinates(event.data));
    }

    // Add method to update max path index
    updateMaxPathIndex(index) {
        if (index > this.maxPathIndex) {
            this.maxPathIndex = index;
        }
    }

    // Add method to get max path index
    getMaxPathIndex() {
        return this.maxPathIndex;
    }

    updateTricycleState(tricycleId, newState) {
        // Remove from all states first
        Object.values(this.tricycleStates).forEach(set => set.delete(tricycleId));
        // Add to new state
        this.tricycleStates[newState].add(tricycleId);
        // Update the display immediately
        this.visualManager.updateTricycleStatus(this.tricycleStates);
    }
}

// ===== Visual Management =====
export class VisualManager {
    constructor() {
        this.markers = {
            appear: new Map(),    // Store passenger appear markers
            load: new Map(),      // Store load markers
            dropoff: new Map(),   // Store dropoff markers
            enqueueLines: new Map(), // Store lines connecting trikes to enqueued passengers
            event: new Map(),     // Store all event markers
            roamPath: new Map(),   // Store roam paths for trikes
            trike: new Map(),      // Add trike markers map
            terminal: new Map()    // Add terminal markers map
        };
    }

    // Marker Management
    addMarker(type, id, marker) {
        if (!this.markers[type]) {
            console.error(`Invalid marker type: ${type}`);
            return;
        }
        if (!marker || !marker.getLatLng) {
            console.error(`Invalid marker object for ${id}`);
            return;
        }
        this.markers[type].set(id, marker);
    }

    removeMarker(type, id) {
        const marker = this.markers[type].get(id);
        if (marker) {
            marker.remove();
            this.markers[type].delete(id);
        }
    }

    getMarker(type, id) {
        return this.markers[type].get(id);
    }

    // Enqueue Line Management
    removeEnqueueLine(passengerId) {
        const lineData = this.markers.enqueueLines.get(passengerId);
        if (lineData && lineData.line) {
            console.log(`Removing enqueue line for passenger ${passengerId}`);
            lineData.line.remove();
            this.markers.enqueueLines.delete(passengerId);
        }
    }

    createEnqueueLine(trikeId, passengerId, trikePos, passengerPos) {
        // Validate all inputs
        if (!trikeId || !passengerId) {
            console.error('Missing trikeId or passengerId for enqueue line');
            return;
        }

        if (!trikePos || !passengerPos) {
            console.error('Missing positions for enqueue line:', { trikePos, passengerPos });
            return;
        }

        if (!isValidCoordinates([trikePos.lat, trikePos.lng]) || 
            !isValidCoordinates([passengerPos.lat, passengerPos.lng])) {
            console.error(`Invalid coordinates for enqueue line:`, { trikePos, passengerPos });
            return;
        }

        // Check if passenger's appear marker exists
        const passengerMarker = this.getMarker('appear', passengerId);
        if (!passengerMarker) {
            // For initial enqueue events, wait a frame for appear markers to be created
            setTimeout(() => {
                const delayedMarker = this.getMarker('appear', passengerId);
                if (delayedMarker) {
                    this.createEnqueueLine(trikeId, passengerId, trikePos, passengerPos);
                }
            }, 0);
            return;
        }

        // Check if this trike already has an enqueue line
        let existingPassengerId = null;
        this.markers.enqueueLines.forEach((lineData, pid) => {
            if (lineData.trikeId === trikeId) {
                existingPassengerId = pid;
            }
        });

        // If this trike already has an enqueue line, remove it first
        if (existingPassengerId) {
            this.removeEnqueueLine(existingPassengerId);
        }

        // Create and store the enqueue line
        const line = L.polyline([trikePos, passengerPos], {
            color: 'red',
            weight: 4,
            opacity: 0.8,
            dashArray: '5, 10',
            interactive: false
        }).addTo(map);

        this.markers.enqueueLines.set(passengerId, {
            trikeId: trikeId,
            line: line,
            lastUpdate: Date.now()
        });

        // Update trike color to red (status 5 = ENQUEUING)
        const trikeMarker = this.getMarker('trike', trikeId);
        if (trikeMarker) {
            this.updateTrikeColor(trikeMarker, 5);
        }
    }

    updateEnqueueLines(trikeId, trikePos) {
        if (!trikePos || !isValidCoordinates([trikePos.lat, trikePos.lng])) {
            console.warn(`Invalid trike position for updating enqueue lines:`, trikePos);
            return;
        }

        // Find and update the enqueue line for this trike
        this.markers.enqueueLines.forEach((lineData, passengerId) => {
            if (lineData.trikeId === trikeId && lineData.line) {
                const passengerMarker = this.getMarker('appear', passengerId);
                if (!passengerMarker) {
                    // Passenger has been loaded, remove the enqueue line
                    this.removeEnqueueLine(passengerId);
                    return;
                }

                const passengerPos = passengerMarker.getLatLng();
                if (passengerPos && isValidCoordinates([passengerPos.lat, passengerPos.lng])) {
                    lineData.line.setLatLngs([trikePos, passengerPos]);
                    lineData.lastUpdate = Date.now();
                } else {
                    // Remove line if passenger position is invalid
                    this.removeEnqueueLine(passengerId);
                }
            }
        });
    }

    // UI Updates
    updatePassengerStatus(passengerStates) {
        const statusPanel = document.getElementById('passenger-status');
        if (!statusPanel) return;

        // Clear existing content
        statusPanel.innerHTML = '';

        // Create status rows
        const statusRows = document.createElement('div');
        statusRows.className = 'status-rows';
        
        // Create status groups with labels
        const states = ['WAITING', 'ENQUEUED', 'ONBOARD', 'COMPLETED'];
        states.forEach(state => {
            const group = document.createElement('div');
            group.className = `status-group ${state.toLowerCase()}`;
            
            const label = document.createElement('div');
            label.className = 'status-label';
            label.textContent = state;
            
            const count = document.createElement('div');
            count.className = 'status-count';
            count.textContent = '(0)';
            
            const members = document.createElement('div');
            members.className = 'status-members';
            
            group.appendChild(label);
            group.appendChild(count);
            group.appendChild(members);
            statusRows.appendChild(group);
        });

        statusPanel.appendChild(statusRows);

        // Update each status group
        const groups = {
            WAITING: statusPanel.querySelector('.waiting'),
            ENQUEUED: statusPanel.querySelector('.enqueued'),
            ONBOARD: statusPanel.querySelector('.onboard'),
            COMPLETED: statusPanel.querySelector('.completed')
        };

        // Update each group's content
        Object.entries(passengerStates).forEach(([state, passengers]) => {
            const group = groups[state];
            if (!group) return;

            // Update count
            const count = group.querySelector('.status-count');
            if (count) {
                count.textContent = `(${passengers.size})`;
            }

            // Update members
            const members = group.querySelector('.status-members');
            if (members) {
                members.innerHTML = '';

                // Convert passenger IDs to numbers and sort them
                const sortedPassengers = Array.from(passengers)
                    .map(id => parseInt(id.replace('passenger_', '')))
                    .sort((a, b) => a - b);

                // Create passenger elements
                sortedPassengers.forEach(num => {
                    const passenger = document.createElement('div');
                    passenger.className = 'passenger-id';
                    passenger.textContent = `P${num}`;
                    members.appendChild(passenger);
                });
            }
        });
    }

    updateTricycleStatus(tricycleStates) {
        const statusPanel = document.getElementById('tricycle-status');
        if (!statusPanel) return;

        // Clear existing content
        statusPanel.innerHTML = '';

        // Create status rows
        const statusRows = document.createElement('div');
        statusRows.className = 'status-rows';
        
        // Create status groups with labels - reordered to show DEFAULT last
        const states = ['ENQUEUEING', 'SERVING', 'DEFAULT'];
        states.forEach(state => {
            const group = document.createElement('div');
            group.className = `status-group ${state.toLowerCase()}`;
            
            const label = document.createElement('div');
            label.className = 'status-label';
            label.textContent = state;
            
            const count = document.createElement('div');
            count.className = 'status-count';
            count.textContent = '(0)';
            
            const members = document.createElement('div');
            members.className = 'status-members';
            
            group.appendChild(label);
            group.appendChild(count);
            group.appendChild(members);
            statusRows.appendChild(group);
        });

        statusPanel.appendChild(statusRows);

        // Update each status group
        const groups = {
            DEFAULT: statusPanel.querySelector('.default'),
            ENQUEUEING: statusPanel.querySelector('.enqueueing'),
            SERVING: statusPanel.querySelector('.serving')
        };

        // Update each group's content
        Object.entries(tricycleStates).forEach(([state, tricycles]) => {
            const group = groups[state];
            if (!group) return;

            // Update count
            const count = group.querySelector('.status-count');
            if (count) {
                count.textContent = `(${tricycles.size})`;
            }

            // Update members
            const members = group.querySelector('.status-members');
            if (members) {
                members.innerHTML = '';

                // Convert tricycle IDs to numbers and sort them
                const sortedTricycles = Array.from(tricycles)
                    .map(id => parseInt(id.replace('trike_', '')))
                    .sort((a, b) => a - b);

                // Create tricycle elements
                sortedTricycles.forEach(num => {
                    const tricycle = document.createElement('div');
                    tricycle.className = 'tricycle-id';
                    
                    // Get the trike marker to check for passengers
                    const trikeId = `trike_${num}`;
                    const trikeMarker = this.getMarker('trike', trikeId);
                    let passengerInfo = '';
                    
                    if (trikeMarker && trikeMarker.getTooltip) {
                        const tooltip = trikeMarker.getTooltip();
                        if (tooltip && tooltip.getContent) {
                            const content = tooltip.getContent();
                            // Extract passenger numbers from tooltip content
                            const passengerMatch = content.match(/P\d+/g);
                            if (passengerMatch) {
                                passengerInfo = ` (${passengerMatch.join(' ')})`;
                            }
                        }
                    }
                    
                    tricycle.textContent = `T${num}${passengerInfo}`;
                    members.appendChild(tricycle);
                });
            }
        });
    }

    reset() {
        // Remove all markers
        Object.values(this.markers).forEach(markerMap => {
            markerMap.forEach(marker => {
                if (marker.remove) marker.remove();
                else if (marker.line) {
                    marker.line.remove();
                    marker.startMarker.remove();
                    marker.endMarker.remove();
                }
            });
            markerMap.clear();
        });
    }

    // Add method to create roam path visualization
    createRoamPath(path) {
        if (!Array.isArray(path) || path.length < 2) {
            console.error('Invalid path for roam visualization');
            return null;
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

        return {
            line: line,
            startMarker: startMarker,
            endMarker: endMarker
        };
    }

    // Add method to update trike marker color
    updateTrikeColor(marker, status) {
        // Check if this trike has any active enqueue lines
        for (const [passengerId, lineData] of this.markers.enqueueLines) {
            if (lineData.trikeId === marker.id) {
                marker.setIcon(L.divIcon({
                    className: 'trike-marker',
                    html: `<div style="
                        width: 12px;
                        height: 12px;
                        border-radius: 50%;
                        border: 4px solid red;
                        background-color: transparent;
                    "></div>`
                }));
                return;
            }
        }

        // Otherwise, use the normal status-based coloring
        let color;
        switch(status) {
            case 'DEFAULT':
                color = 'green';
                break;
            case 'ENQUEUEING':
                color = 'red';
                break;
            case 'SERVING':
                color = 'orange';
                break;
            default:
                color = 'green';
        }

        marker.setIcon(L.divIcon({
            className: 'trike-marker',
            html: `<div style="
                width: 12px;
                height: 12px;
                border-radius: 50%;
                border: 4px solid ${color};
                background-color: transparent;
            "></div>`
        }));
    }

    // Add method to update trike tooltip
    updateTrikeTooltip(marker, id, passengers) {
        const trikeNum = id.split('_')[1];
        const passengerList = Array.from(passengers).sort((a, b) => {
            const numA = parseInt(a.split('_')[1]);
            const numB = parseInt(b.split('_')[1]);
            return numA - numB;
        }).map(p => `P${p.split('_')[1]}`).join(' ');
        
        marker.unbindTooltip();
        const tooltipText = passengers.size > 0 ? `T${trikeNum} (${passengerList})` : `T${trikeNum}`;
        marker.bindTooltip(tooltipText, {
            permanent: false,
            direction: 'top'
        });
    }

    // Add method to update metadata content
    updateMetadata(metadata, summary) {
        const metadataContent = document.getElementById('metadataContent');
        metadataContent.innerHTML = '';

        // Create simulation summary section
        const summarySection = document.createElement('div');
        summarySection.className = 'metadata-section';
        summarySection.innerHTML = `
            <h3>Simulation Summary</h3>
            <table class="metadata-table">
                <tr><td>Total Trips Completed:</td><td>${summary.total_trips_completed}</td></tr>
                <tr><td>Completion Rate:</td><td>${summary.completion_rate.toFixed(1)}%</td></tr>
                <tr><td>Average Wait Time:</td><td>${summary.average_wait_time.toFixed(1)}s</td></tr>
                <tr><td>Average Travel Time:</td><td>${summary.average_travel_time.toFixed(1)}s</td></tr>
                <tr><td>Total Distance:</td><td>${summary.total_distance_km.toFixed(1)}km</td></tr>
                <tr><td>Productive Distance:</td><td>${summary.productive_distance_km.toFixed(1)}km</td></tr>
                <tr><td>Efficiency:</td><td>${summary.efficiency_percentage.toFixed(1)}%</td></tr>
                <tr><td>Active Tricycles:</td><td>${summary.active_tricycles}</td></tr>
            </table>
        `;
        metadataContent.appendChild(summarySection);

        // Create simulation parameters section
        const paramsSection = document.createElement('div');
        paramsSection.className = 'metadata-section';
        paramsSection.innerHTML = `
            <h3>Simulation Parameters</h3>
            <table class="metadata-table">
                <tr><td>Total Tricycles:</td><td>${metadata.totalTrikes}</td></tr>
                <tr><td>Total Terminals:</td><td>${metadata.totalTerminals}</td></tr>
                <tr><td>Total Passengers:</td><td>${metadata.totalPassengers}</td></tr>
                <tr><td>Smart Scheduling:</td><td>${metadata.smartScheduling ? 'Yes' : 'No'}</td></tr>
                <tr><td>Tricycle Capacity:</td><td>${metadata.trikeConfig.capacity}</td></tr>
                <tr><td>Realistic Mode:</td><td>${metadata.isRealistic ? 'Yes' : 'No'}</td></tr>
                <tr><td>Fixed Hotspots:</td><td>${metadata.useFixedHotspots ? 'Yes' : 'No'}</td></tr>
                <tr><td>Fixed Terminals:</td><td>${metadata.useFixedTerminals ? 'Yes' : 'No'}</td></tr>
                <tr><td>Road Passenger Chance:</td><td>${metadata.roadPassengerChance}</td></tr>
                <tr><td>Roaming Tricycle Chance:</td><td>${metadata.roamingTrikeChance}</td></tr>
                <tr><td>Servicing Enqueue Radius:</td><td>${metadata.trikeConfig.s_enqueue_radius_meters}m</td></tr>
                <tr><td>Regular Enqueue Radius:</td><td>${metadata.trikeConfig.enqueue_radius_meters}m</td></tr>
                <tr><td>Max Cycles:</td><td>${metadata.trikeConfig.maxCycles}</td></tr>
            </table>
        `;
        metadataContent.appendChild(paramsSection);
    }

    // Add event logging functionality
    logEvent(time, id, type, data) {
        // Skip logging MOVE events
        if (type === 'MOVE' || type === "WAIT") {
            return;
        }

        const eventLog = document.getElementById('eventLog');
        if (!eventLog) return;

        const entry = document.createElement('div');
        entry.className = 'event-log-entry';
        entry.setAttribute('data-event-type', type);
        
        // Create a grid layout for the event log entry
        entry.innerHTML = `
            <span class="event-frame">[${time}]</span>
            <span class="event-id">${id}</span>
            <span class="event-type">${type}</span>
            <span class="event-data">${data ? (typeof data === 'string' ? data : 
                (data.location ? `[${data.location[0].toFixed(6)}, ${data.location[1].toFixed(6)}]` :
                (data.coordinates ? `[${data.coordinates[0].toFixed(6)}, ${data.coordinates[1].toFixed(6)}]` : ''))) : ''}</span>
        `;
        
        eventLog.appendChild(entry);
        eventLog.scrollTop = eventLog.scrollHeight;
    }

    // Add method to create event marker
    createEventMarker(lat, lng, message, id) {
        console.log('Creating event marker:', { lat, lng, message, id });
        
        // Only skip enqueue events, not passenger appear events
        if (message.includes("ENQUEUE")) {
            console.log('Skipping ENQUEUE event');
            return null;
        }

        // Validate coordinates
        if (!isValidCoordinates([lat, lng])) {
            console.warn(`Invalid coordinates for marker: ${lat}, ${lng}`);
            return null;
        }

        const key = `${lat.toFixed(6)},${lng.toFixed(6)}`;
        if (!window.tooltipStackCounter) window.tooltipStackCounter = {};
        if (!window.tooltipStackCounter[key]) window.tooltipStackCounter[key] = 0;
        const offset = window.tooltipStackCounter[key] * 24; // 24px per stacked tooltip
        window.tooltipStackCounter[key] += 1;

        // Extract frame number from message
        const frameMatch = message.match(/\[Frame (\d+)\]/);
        const frameNumber = frameMatch ? frameMatch[1] : '0';

        // Extract event type and IDs
        let eventType = '';
        let passengerId = '';
        let trikeId = '';
        
        // First check if the id parameter is a trike
        if (id && id.startsWith('trike_')) {
            trikeId = `T${id.split('_')[1]}`;
        }
        
        if (message.includes('APPEAR')) {
            eventType = 'APPEAR';
            // For APPEAR events, use the id parameter
            if (id.startsWith('trike_')) {
                trikeId = `T${id.split('_')[1]}`;
            } else if (id.startsWith('passenger_')) {
                passengerId = `P${id.split('_')[1]}`;
            }
        } else if (message.includes('NEW_ROAM_PATH')) {
            eventType = 'NEW_ROAM_PATH';
            if (id.startsWith('trike_')) {
                trikeId = `T${id.split('_')[1]}`;
            }
        } else if (message.includes('LOAD')) {
            eventType = 'LOAD';
            // Extract trike ID from the message if not already set
            if (!trikeId) {
                const trikeMatch = message.match(/trike_(\d+)/);
                if (trikeMatch) {
                    trikeId = `T${trikeMatch[1]}`;
                }
            }
            // Extract passenger ID from the message
            const passengerMatch = message.match(/passenger_(\d+)/);
            if (passengerMatch) {
                passengerId = `P${passengerMatch[1]}`;
            }
        } else if (message.includes('DROP-OFF')) {
            eventType = 'DROP-OFF';
            // Extract trike ID from the message if not already set
            if (!trikeId) {
                const trikeMatch = message.match(/trike_(\d+)/);
                if (trikeMatch) {
                    trikeId = `T${trikeMatch[1]}`;
                }
            }
            // Extract passenger ID from the message
            const passengerMatch = message.match(/passenger_(\d+)/);
            if (passengerMatch) {
                passengerId = `P${passengerMatch[1]}`;
            }
        }

        console.log('Extracted IDs:', { trikeId, passengerId });

        // Format the tooltip text
        let tooltipText = `[${frameNumber}]`;
        if (trikeId) {
            tooltipText += ` ${trikeId}`;
        }
        tooltipText += ` ${eventType}`;
        if (passengerId) {
            tooltipText += ` ${passengerId}`;
        }
        console.log('Tooltip text:', tooltipText);

        // Determine marker color based on event type
        const isLoad = message.includes("LOAD");
        const isDropoff = message.includes("DROP-OFF");
        const isPassengerAppear = message.includes("APPEAR") && id.startsWith("passenger");
        const isTrikeAppear = message.includes("APPEAR") && id.startsWith("trike");
        const isEnqueue = message.includes("ENQUEUE") && id.startsWith("passenger");
        const isReset = message.includes("RESET") && id.startsWith("passenger");

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
        
        // Create the marker
        const marker = L.marker([lat, lng], {
            icon: L.divIcon({
                className: 'event-marker',
                html: `<div style="background-color: ${markerColor}; width: 8px; height: 8px; border-radius: 50%;"></div>`,
                iconSize: [8, 8],
                iconAnchor: [4, 4]
            })
        });

        // Add to map if it exists
        if (window.map) {
            console.log('Adding marker to map');
            marker.addTo(window.map);
        } else {
            console.error('Map not initialized when creating marker');
            return null;
        }

        // Add tooltip with new format
        marker.bindTooltip(tooltipText, {
            permanent: false,
            direction: 'top',
            className: 'event-tooltip-stacked',
            offset: [0, -offset]
        });

        // Handle load and drop-off events
        if (isLoad || isDropoff) {
            const match = message.match(/passenger_\d+/);
            if (match) {
                const passengerId = match[0];
                // Remove the appear marker for this passenger
                const appearMarker = this.markers.appear.get(passengerId);
                if (appearMarker) {
                    appearMarker.remove();
                    this.markers.appear.delete(passengerId);
                }
                // Store the new marker
                this.addMarker(isLoad ? 'load' : 'dropoff', passengerId, marker);
            }
        } else if (isPassengerAppear) {
            console.log('Adding passenger appear marker to appear map');
            this.addMarker('appear', id, marker);
        }

        return marker;
    }

    // Add method to track event markers
    addEventMarker(marker) {
        if (!marker) return;
        const id = `event_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        this.markers.event.set(id, marker);
        return id;
    }

    // Add method to remove event markers
    removeEventMarkers() {
        this.markers.event.forEach(marker => marker.remove());
        this.markers.event.clear();
    }

    // Add method to manage roam paths
    setRoamPath(trikeId, path) {
        // Remove existing roam path if any
        this.removeRoamPath(trikeId);

        if (!Array.isArray(path) || path.length < 2) {
            console.error('Invalid path for roam visualization');
            return;
        }

        const roamPath = this.createRoamPath(path);
        if (roamPath) {
            this.markers.roamPath.set(trikeId, roamPath);
        }
    }

    removeRoamPath(trikeId) {
        const roamPath = this.markers.roamPath.get(trikeId);
        if (roamPath) {
            roamPath.line.remove();
            roamPath.startMarker.remove();
            roamPath.endMarker.remove();
            this.markers.roamPath.delete(trikeId);
        }
    }

    // Add method to create trike marker
    createTrikeMarker(id, initialCoords) {
        const markerIcon = L.divIcon({
            className: 'trike-marker',
            html: `<div style="
                width: 12px;
                height: 12px;
                border-radius: 50%;
                border: 4px solid rgba(68, 255, 68, 1);
                background-color: transparent;
            "></div>`
        });

        const marker = L.marker(initialCoords, { icon: markerIcon });
        this.addMarker('trike', id, marker);
        return marker;
    }

    // Add method to validate and process event timing
    processEventTiming(event, currentTime) {
        if (!event || !event.time) return false;
        return event.time * REFRESH_TIME <= currentTime;
    }

    // Add method to update frame counter
    updateFrameCounter(frame) {
        const frameCounter = document.getElementById('frameCounter');
        if (frameCounter) {
            frameCounter.textContent = `Frame: ${frame}`;
        }
    }

    // Add method to clear all markers
    clearAllMarkers() {
        Object.values(this.markers).forEach(markerMap => {
            markerMap.forEach(marker => {
                if (marker.remove) marker.remove();
                else if (marker.line) {
                    marker.line.remove();
                    marker.startMarker.remove();
                    marker.endMarker.remove();
                }
            });
            markerMap.clear();
        });
    }

    // Add method to update trike position
    updateTrikePosition(trikeId, position, pathIndex) {
        const marker = this.getMarker('trike', trikeId);
        if (marker) {
            marker.setLatLng(position);
            // Update max path index in state manager
            stateManager.updateMaxPathIndex(pathIndex);
        }
    }
}

// Create singleton instances
export const visualManager = new VisualManager();
export const stateManager = new StateManager(visualManager); 