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
    constructor() {
        this.passengerStates = {
            WAITING: new Set(),
            ENQUEUED: new Set(),
            ONBOARD: new Set(),
            COMPLETED: new Set()
        };
        this.trikeStates = new Map();
        this.maxPathIndex = 0;  // Track maximum path index
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
        this.trikeStates.clear();
        this.maxPathIndex = 0;  // Reset max path index
    }

    // Add method to track trike passengers
    updateTrikePassengers(trikeId, passengers) {
        this.trikeStates.set(trikeId, new Set(passengers));
    }

    getTrikePassengers(trikeId) {
        return this.trikeStates.get(trikeId) || new Set();
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
    createEnqueueLine(trikeId, passengerId, trikePos, passengerPos) {
        if (!isValidCoordinates([trikePos.lat, trikePos.lng]) || 
            !isValidCoordinates([passengerPos.lat, passengerPos.lng])) {
            console.error(`Invalid coordinates for enqueue line:`, { trikePos, passengerPos });
            return;
        }

        const line = L.polyline([trikePos, passengerPos], {
            color: 'red',
            weight: 2,
            opacity: 1,
            dashArray: '5, 10'
        }).addTo(map);
        
        this.markers.enqueueLines.set(passengerId, {
            trikeId: trikeId,
            line: line
        });
    }

    updateEnqueueLine(passengerId, trikePos, passengerPos) {
        if (!isValidCoordinates([trikePos.lat, trikePos.lng]) || 
            !isValidCoordinates([passengerPos.lat, passengerPos.lng])) {
            console.error(`Invalid coordinates for updating enqueue line:`, { trikePos, passengerPos });
            return;
        }

        const lineData = this.markers.enqueueLines.get(passengerId);
        if (lineData && lineData.line) {
            lineData.line.setLatLngs([trikePos, passengerPos]);
        }
    }

    removeEnqueueLine(passengerId) {
        const lineData = this.markers.enqueueLines.get(passengerId);
        if (lineData) {
            lineData.line.remove();
            this.markers.enqueueLines.delete(passengerId);
        }
    }

    // UI Updates
    updatePassengerStatus(passengerStates) {
        const statusPanel = document.getElementById('passenger-status');
        if (!statusPanel) return;

        // Create status rows if they don't exist
        if (!statusPanel.querySelector('.status-rows')) {
            const statusRows = document.createElement('div');
            statusRows.className = 'status-rows';
            
            // Create labels
            const labels = document.createElement('div');
            labels.className = 'status-labels';
            labels.innerHTML = `
                <div>WAITING</div>
                <div>ENQUEUED</div>
                <div>ONBOARD</div>
                <div>COMPLETED</div>
            `;
            statusRows.appendChild(labels);

            // Create content
            const content = document.createElement('div');
            content.className = 'status-content';
            content.innerHTML = `
                <div class="status-group waiting"></div>
                <div class="status-group enqueued"></div>
                <div class="status-group onboard"></div>
                <div class="status-group completed"></div>
            `;
            statusRows.appendChild(content);

            statusPanel.appendChild(statusRows);
        }

        // Update each status group
        const groups = {
            WAITING: statusPanel.querySelector('.waiting'),
            ENQUEUED: statusPanel.querySelector('.enqueued'),
            ONBOARD: statusPanel.querySelector('.onboard'),
            COMPLETED: statusPanel.querySelector('.completed')
        };

        // Clear existing content
        Object.values(groups).forEach(group => {
            if (group) group.innerHTML = '';
        });

        // Add passengers to their respective groups
        Object.entries(passengerStates).forEach(([state, passengers]) => {
            const group = groups[state];
            if (!group) return;

            // Convert passenger IDs to numbers and sort them
            const sortedPassengers = Array.from(passengers)
                .map(id => parseInt(id.replace('passenger_', '')))
                .sort((a, b) => a - b);

            // Create passenger elements
            sortedPassengers.forEach(num => {
                const passenger = document.createElement('div');
                passenger.className = 'passenger-id';
                passenger.textContent = num;
                group.appendChild(passenger);
            });
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
        let color;
        switch(status) {
            case 0: // IDLE
                color = '#0000FF'; // Blue
                break;
            case 1: // SERVING
                color = '#FFA500'; // Orange
                break;
            case 2: // TERMINAL
                color = '#0000FF'; // Blue
                break;
            case 3: // ROAMING
                color = '#0000FF'; // Blue
                break;
            case 4: // RETURNING
                color = '#0000FF'; // Blue
                break;
            case 5: // ENQUEUING
                color = '#FF0000'; // Red
                break;
            default:
                color = '#0000FF'; // Default to blue
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

        marker.setIcon(markerIcon);
    }

    // Add method to update trike tooltip
    updateTrikeTooltip(marker, id, passengers) {
        const passengerList = Array.from(passengers).sort((a, b) => {
            const numA = parseInt(a.split('_')[1]);
            const numB = parseInt(b.split('_')[1]);
            return numA - numB;
        }).join(' ');
        
        marker.unbindTooltip();
        marker.bindTooltip(`${id}: ${passengerList}`, {
            permanent: false,
            direction: 'top'
        });
    }

    // Add event logging functionality
    logEvent(time, id, type, data) {
        const eventLog = document.getElementById('eventLog');
        if (!eventLog) return;

        const entry = document.createElement('div');
        entry.className = 'event-log-entry';
        entry.setAttribute('data-event-type', type);
        
        // Format the event message with frame, id, type, and data
        let message = `[Frame ${time}] `;
        
        // Add entity type prefix
        if (id.startsWith('trike')) {
            message += `🚲 ${id}: `;
        } else if (id.startsWith('passenger')) {
            message += `👤 ${id}: `;
        } else {
            message += `${id}: `;
        }
        
        // Add event type with appropriate emoji
        switch (type) {
            case 'APPEAR':
                message += '📍 APPEAR';
                break;
            case 'NEW_ROAM_PATH':
                message += '🛣️ NEW_ROAM_PATH';
                break;
            case 'ENQUEUE':
                message += '⏳ ENQUEUE';
                break;
            case 'MOVE':
                message += `🚶 MOVE (${data} frames)`;
                break;
            case 'LOAD':
                message += `⬆️ LOAD ${data}`;
                break;
            case 'WAIT':
                message += `⏸️ WAIT (${data} frames)`;
                break;
            case 'DROP-OFF':
                message += `⬇️ DROP-OFF ${data}`;
                break;
            default:
                message += type;
        }
        
        // Add location data if available
        if (data && typeof data === 'object' && data.location) {
            message += ` at [${data.location[0].toFixed(6)}, ${data.location[1].toFixed(6)}]`;
        }
        
        entry.textContent = message;
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

        // Determine marker color based on event type
        const isLoad = message.includes("LOAD");
        const isDropoff = message.includes("DROP-OFF");
        const isPassengerAppear = message.includes("APPEAR") && id.startsWith("passenger");
        const isTrikeAppear = message.includes("APPEAR") && id.startsWith("trike");
        const isEnqueue = message.includes("ENQUEUE") && id.startsWith("passenger");
        const isReset = message.includes("RESET") && id.startsWith("passenger");

        console.log('Event type detection:', {
            isLoad,
            isDropoff,
            isPassengerAppear,
            isTrikeAppear,
            isEnqueue,
            isReset
        });

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
        
        // Create the marker - coordinates are in [lat, lng] format as received
        const marker = L.marker([lat, lng], {
            icon: L.divIcon({
                className: 'event-marker',
                html: `<div style="background-color: ${markerColor}; width: 8px; height: 8px; border-radius: 50%;"></div>`,
                iconSize: [8, 8],
                iconAnchor: [4, 4]  // Center the icon
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

        // Add tooltip
        marker.bindTooltip(message, {
            permanent: false, // Only show on hover
            direction: 'top',
            className: 'event-tooltip-stacked',
            offset: [0, -offset]
        });

        // Store marker in appropriate map
        if (isPassengerAppear) {
            console.log('Adding passenger appear marker to appear map');
            this.addMarker('appear', id, marker);
        } else if (isLoad) {
            const match = message.match(/passenger_\d+/);
            if (match) {
                this.addMarker('load', match[0], marker);
            }
        } else if (isDropoff) {
            const match = message.match(/passenger_\d+/);
            if (match) {
                this.addMarker('dropoff', match[0], marker);
            }
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
                border: 4px solid #0000FF;
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

    // Add method to update enqueue lines for a trike
    updateEnqueueLines(trikeId, trikePos) {
        this.markers.enqueueLines.forEach((lineData, passengerId) => {
            if (lineData.trikeId === trikeId) {
                const passengerMarker = this.getMarker('appear', passengerId);
                if (passengerMarker) {
                    this.updateEnqueueLine(passengerId, trikePos, passengerMarker.getLatLng());
                }
            }
        });
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
export const stateManager = new StateManager();
export const visualManager = new VisualManager(); 