/**
 * Event Processing Module
 * 
 * This module handles all event processing and routing for the visualization system.
 * It coordinates between state management and visual updates.
 */

import { stateManager, visualManager } from './managers.js';

// Utility function to convert point coordinates to raw [lat, lng] format
function pointsToRaw(point) {
    if (!point) return null;
    
    let coords;
    if (point.type === 'point' && Array.isArray(point.data)) {
        coords = point.data;
    } else if (Array.isArray(point)) {
        coords = point;
    } else {
        console.error('Invalid point format:', point);
        return null;
    }
    
    if (!coords || coords.length !== 2) {
        console.error('Invalid coordinates array:', coords);
        return null;
    }
    
    // Convert [lng, lat] to [lat, lng] for Leaflet
    return [coords[1], coords[0]];
}

export class EventProcessor {
    constructor() {
        this.stateManager = stateManager;
        this.visualManager = visualManager;
        this.eventHandlers = new Map();
        this.setupDefaultHandlers();
    }

    setupDefaultHandlers() {
        // Add initialization handlers
        this.registerHandler('INITIALIZE_SIMULATION', (event) => {
            const { passengers, trikes } = event.data;
            
            // Initialize passengers
            passengers.forEach(passenger => {
                console.log('Creating marker for passenger:', passenger.id, 'src:', passenger.src);
                
                // Convert coordinates using utility function
                const coords = pointsToRaw(passenger.src);
                if (!coords) {
                    console.error('Failed to convert coordinates for passenger:', passenger.id);
                    return;
                }
                
                console.log('Converted coordinates:', coords);
                const marker = this.visualManager.createEventMarker(
                    coords[0],  // latitude
                    coords[1],  // longitude
                    `${passenger.id}: APPEAR`,
                    passenger.id
                );
                
                if (marker) {
                    console.log('Successfully created marker for passenger:', passenger.id);
                    // Add to visual manager
                    this.visualManager.addMarker('appear', passenger.id, marker);
                    
                    // Update state
                    this.stateManager.updatePassengerState(passenger.id, 'WAITING');
                } else {
                    console.error('Failed to create marker for passenger:', passenger.id);
                }
            });

            // Initialize trikes
            trikes.forEach(trike => {
                console.log('Creating marker for trike:', trike.id, 'path:', trike.path);
                
                // Validate and process path coordinates
                const processedPath = trike.path.map(coord => {
                    if (Array.isArray(coord)) {
                        // Convert [lat, lng] to [lng, lat] for OSRM format
                        return [coord[1], coord[0]];
                    } else if (coord?.type === 'point' && Array.isArray(coord.data)) {
                        // OSRM point format - already in [lng, lat]
                        return coord.data;
                    }
                    console.error('Invalid coordinate format for trike:', trike.id, coord);
                    return null;
                }).filter(coord => coord !== null);

                if (processedPath.length === 0) {
                    console.error('No valid coordinates in path for trike:', trike.id);
                    return;
                }

                console.log('Processed path for trike:', trike.id, processedPath);
                
                // Create moving marker
                const marker = L.movingMarker(
                    trike.id,
                    processedPath,
                    trike.createTime,
                    Infinity,
                    trike.speed,
                    trike.events
                );
                
                if (!marker) {
                    console.error(`Failed to create marker for trike ${trike.id}`);
                    return;
                }
                
                // Add to map
                marker.addTo(window.map);
                
                // Add to visual manager first
                this.visualManager.addMarker('trike', trike.id, marker);
                
                // Start animation after a short delay to ensure proper initialization
                setTimeout(() => {
                    console.log(`Starting animation for trike ${trike.id}`);
                    marker._startAnimation();
                }, 100);
            });

            // Update UI
            this.visualManager.updatePassengerStatus(this.stateManager.passengerStates);
        });

        // Add terminal initialization handler
        this.registerHandler('INITIALIZE_TERMINALS', (event) => {
            event.data.forEach(terminal => {
                const marker = L.marker(terminal.location, {
                    icon: L.divIcon({
                        className: 'terminal-marker',
                        html: `<div style="
                            width: 12px;
                            height: 12px;
                            border-radius: 50%;
                            border: 4px solid #FF0000;
                            background-color: transparent;
                        "></div>`
                    })
                }).addTo(window.map);

                marker.bindTooltip(
                    `Terminal ${terminal.id}: ${terminal.remaining_passengers} passengers, ${terminal.remaining_tricycles} tricycles`,
                    { permanent: false }
                );

                this.visualManager.addMarker('terminal', `terminal_${terminal.id}`, marker);
            });
        });

        // Add INIT_MARKER handler
        this.registerHandler('INIT_MARKER', (event) => {
            const { type, id, path, isTrike } = event;
            if (isTrike && this.stateManager.isValidCoordinates(path[0])) {
                return this.visualManager.createTrikeMarker(id, path[0]);
            }
            return null;
        });

        // Combine passenger state update handlers
        this.registerHandler('UPDATE_PASSENGER', (event) => {
            const { passengerId, newState, trikeId, passengers } = event;
            
            // Update passenger state
            this.stateManager.updatePassengerState(passengerId, newState);
            
            // Update trike state if provided
            if (trikeId && passengers) {
                this.stateManager.updateTrikePassengers(trikeId, passengers);
                const marker = this.visualManager.getMarker('trike', trikeId);
                if (marker) {
                    this.visualManager.updateTrikeTooltip(marker, trikeId, passengers);
                }
            }
            
            // Update visual status
            this.visualManager.updatePassengerStatus(this.stateManager.passengerStates);
        });

        // Combine marker management handlers
        this.registerHandler('MANAGE_MARKER', (event) => {
            const { type, id, marker, path, isTrike } = event;
            
            switch (type) {
                case 'INIT':
                    if (isTrike && this.stateManager.isValidCoordinates(path[0])) {
                        return this.visualManager.createTrikeMarker(id, path[0]);
                    }
                    return null;
                    
                case 'REMOVE':
                    if (isTrike) {
                        this.visualManager.removeRoamPath(id);
                        this.visualManager.markers.enqueueLines.forEach((lineData, passengerId) => {
                            if (lineData.trikeId === id) {
                                this.visualManager.removeEnqueueLine(passengerId);
                            }
                        });
                    }
                    this.visualManager.removeEventMarkers();
                    break;
                    
                case 'UPDATE_COLOR':
                    if (marker && isTrike) {
                        this.visualManager.updateTrikeColor(marker, event.status);
                    }
                    break;
                    
                case 'UPDATE_TOOLTIP':
                    if (marker && isTrike) {
                        this.visualManager.updateTrikeTooltip(marker, id, event.passengers);
                    }
                    break;
            }
        });

        // Combine event marker handlers
        this.registerHandler('MANAGE_EVENT_MARKER', (event) => {
            const { type, lat, lng, message, id, marker } = event;
            
            switch (type) {
                case 'CREATE':
                    if (!message.includes("ENQUEUE") && this.stateManager.isValidCoordinates([lat, lng])) {
                        const newMarker = this.visualManager.createEventMarker(lat, lng, message, id);
                        if (newMarker) {
                            this.visualManager.addMarker('event', id, newMarker);
                        }
                        return newMarker;
                    }
                    return null;
                    
                case 'TRACK':
                    if (marker) {
                        this.visualManager.addMarker('event', id, marker);
                    }
                    break;
                    
                case 'REMOVE_ALL':
                    this.visualManager.removeEventMarkers();
                    break;
            }
        });

        // Combine path management handlers
        this.registerHandler('MANAGE_PATH', (event) => {
            const { type, trikeId, path } = event;
            
            switch (type) {
                case 'SET_ROAM':
                    if (Array.isArray(path) && path.length >= 2) {
                        this.visualManager.setRoamPath(trikeId, path);
                    }
                    break;
                    
                case 'REMOVE_ROAM':
                    this.visualManager.removeRoamPath(trikeId);
                    break;
                    
                case 'UPDATE_ENQUEUE':
                    const trikePos = event.trikePos;
                    this.visualManager.updateEnqueueLines(trikeId, trikePos);
                    break;
            }
        });

        // Combine movement handlers
        this.registerHandler('PROCESS_MOVEMENT', (event) => {
            const { type, marker, event: markerEvent, timestamp } = event;
            
            switch (type) {
                case 'MOVE':
                    this.handleMoveEvent(marker, markerEvent, timestamp);
                    break;
                    
                case 'WAIT':
                    this.handleWaitEvent(marker, markerEvent, timestamp);
                    break;
                    
                case 'FINISH':
                    this.handleFinishEvent(marker);
                    break;
            }
        });

        // Combine passenger interaction handlers
        this.registerHandler('PROCESS_PASSENGER_INTERACTION', (event) => {
            const { type, marker, event: markerEvent } = event;
            
            switch (type) {
                case 'APPEAR':
                    this.handleAppearEvent(marker, markerEvent, event.timestamp);
                    break;
                    
                case 'PASSENGER_EVENT':
                    this.handlePassengerEvent(marker, markerEvent);
                    break;
            }
        });

        // Add handler for event timing
        this.registerHandler('CHECK_EVENT_TIMING', (event) => {
            return this.visualManager.processEventTiming(event.event, event.currentTime);
        });

        // Add handler for event logging
        this.registerHandler('LOG_EVENT', (event) => {
            const { time, id, type, data } = event;
            this.visualManager.logEvent(time, id, type, data);
        });
    }

    // Event handling methods
    handleAppearEvent(marker, event, timestamp) {
        console.log('Handling appear event for marker:', marker.id, 'at location:', event.location);
        
        const location = marker.id.startsWith("passenger") ? 
            [event.location[1], event.location[0]] : // Convert [x,y] to [lat,lng]
            marker.path[0];
        
        console.log('Setting marker position to:', location);
        marker.setLatLng(location);
        marker.updateTooltip();
        
        const message = `${marker.id}: ${event.type}`;
        marker.createEventMarker(location[0], location[1], message);
        
        // Calculate frame number from event time
        const frame = event.time;
        console.log('Logging appear event:', { frame, id: marker.id, type: event.type });
        marker.logEvent(frame, marker.id, event.type);
    }

    handleMoveEvent(marker, event, timestamp) {
        // Skip move events for passenger appear markers
        if (marker.id.startsWith("passenger")) {
            console.log('Skipping move event for passenger marker:', marker.id);
            return;
        }

        const timeElapsed = timestamp - marker._prevTimeStamp;
        const pathDistanceTravelled = marker.SPEED * timeElapsed;
        const curPoint = marker.path[marker.currentPathIndex];
        const nxtPoint = marker.path[marker.currentPathIndex + 1];
        const segmentProgress = Math.min(1, pathDistanceTravelled / getEuclideanDistance(curPoint, nxtPoint));
        
        this.processEvent({
            type: 'MOVE',
            trikeId: marker.id,
            timeElapsed: timeElapsed,
            curPoint: curPoint,
            nxtPoint: nxtPoint,
            segmentProgress: segmentProgress
        });

        if (Math.round(segmentProgress * 100) == 100) {
            marker._prevTimeStamp = timestamp;
            marker.currentPathIndex += 1;
            event.data -= 1;

            if (event.data == 0) {
                marker.currentEventIndex += 1;
                if (event.isRoam && marker.currentPathIndex > 0) {
                    const startIdx = Math.max(0, marker.currentPathIndex - event.pathLength);
                    const endIdx = Math.min(marker.path.length - 1, marker.currentPathIndex);
                    if (startIdx < endIdx) {
                        const roamPath = marker.path.slice(startIdx, endIdx + 1);
                        if (roamPath.length >= 2) {
                            marker.createRoamPath(roamPath);
                        }
                    }
                }
            }
        }
    }

    handlePassengerEvent(marker, event) {
        // Skip passenger events for passenger appear markers
        if (marker.id.startsWith("passenger")) {
            console.log('Skipping passenger event for passenger marker:', marker.id);
            return;
        }

        const eventPoint = marker.path[marker.currentPathIndex];
        if (eventPoint && Array.isArray(eventPoint) && eventPoint.length === 2) {
            marker.setLatLng(eventPoint);
            
            const message = `${marker.id}: ${event.type} ${event.data || ""}`;
            marker.createEventMarker(eventPoint[0], eventPoint[1], message);
            marker.logEvent(event.time, event.type, event.data);

            if (marker.id.startsWith("trike")) {
                switch (event.type) {
                    case "DROP-OFF":
                        marker.passengers.delete(event.data);
                        this.processEvent({
                            type: 'UPDATE_PASSENGER',
                            passengerId: event.data,
                            newState: 'COMPLETED',
                            trikeId: marker.id,
                            passengers: marker.passengers
                        });
                        break;
                    case "LOAD":
                        marker.passengers.add(event.data);
                        this.processEvent({
                            type: 'UPDATE_PASSENGER',
                            passengerId: event.data,
                            newState: 'ONBOARD',
                            trikeId: marker.id,
                            passengers: marker.passengers
                        });
                        break;
                    case "ENQUEUE":
                        this.processEvent({
                            type: 'UPDATE_PASSENGER',
                            passengerId: event.data,
                            newState: 'ENQUEUED',
                            trikeId: marker.id,
                            passengers: marker.passengers
                        });
                        break;
                }
            }
            
            marker._prevTimeStamp = timestamp;
            marker.currentEventIndex += 1;
        }
    }

    handleWaitEvent(marker, event, timestamp) {
        const timeElapsed = timestamp - marker._prevTimeStamp;
        event.data -= timeElapsed;
        
        this.processEvent({
            type: 'WAIT',
            trikeId: marker.id,
            timeElapsed: timeElapsed,
            waitTime: event.data
        });
        
        if (event.data <= 0) {
            marker.currentEventIndex += 1;
        }
    }

    handleFinishEvent(marker) {
        this.processEvent({
            type: 'FINISH',
            trikeId: marker.id
        });
    }

    registerHandler(eventType, handler) {
        this.eventHandlers.set(eventType, handler);
    }

    processEvent(event) {
        const handler = this.eventHandlers.get(event.type);
        if (handler) {
            handler(event);
        } else {
            console.warn(`No handler registered for event type: ${event.type}`);
        }
    }
}

// Create and export the event processor instance
export const eventProcessor = new EventProcessor(); 