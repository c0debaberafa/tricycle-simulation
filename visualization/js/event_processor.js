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

        // Process trike events
        this.registerHandler('PROCESS_TRIKE_EVENT', (event) => {
            const { marker, event: markerEvent } = event;
            this.handleEvent(marker, markerEvent);
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

    handleEvent(marker, event) {
        // Only process events for trikes
        if (!marker.id.startsWith("trike")) {
            console.log('Skipping event for non-trike marker:', marker.id);
            return;
        }

        const eventPoint = marker.path[marker.currentPathIndex];
        if (eventPoint && Array.isArray(eventPoint) && eventPoint.length === 2) {
            marker.setLatLng(eventPoint);
            
            // Convert [lng, lat] to [lat, lng] for createEventMarker
            const latLng = [eventPoint[1], eventPoint[0]];
            
            switch (event.type) {
                case "LOAD":
                    // Create load event marker
                    const newLoadMarker = this.visualManager.createEventMarker(latLng[0], latLng[1], `${event.data}: ${event.type}`, event.data);
                    if (newLoadMarker) {
                        this.visualManager.addMarker('load', event.data, newLoadMarker);
                    }
                    
                    // Remove enqueue line for this passenger
                    this.visualManager.removeEnqueueLine(event.data);
                    
                    // Update passenger state
                    marker.passengers.add(event.data);
                    // Remove the appear marker for this passenger
                    const appearMarker = this.visualManager.markers.appear.get(event.data);
                    if (appearMarker) {
                        console.log('Removing appear marker for passenger:', event.data);
                        appearMarker.remove();
                        this.visualManager.markers.appear.delete(event.data);
                    } else {
                        console.log('No appear marker found for passenger:', event.data);
                    }
                    this.processEvent({
                        type: 'UPDATE_PASSENGER',
                        passengerId: event.data,
                        newState: 'ONBOARD',
                        trikeId: marker.id,
                        passengers: marker.passengers
                    });
                    break;

                case "DROP-OFF":
                    // Create drop-off event marker
                    const dropoffMarker = this.visualManager.createEventMarker(latLng[0], latLng[1], `${event.data}: ${event.type}`, event.data);
                    if (dropoffMarker) {
                        this.visualManager.addMarker('dropoff', event.data, dropoffMarker);
                    }
                    
                    // Remove the load marker for this passenger
                    const existingLoadMarker = this.visualManager.markers.load.get(event.data);
                    if (existingLoadMarker) {
                        console.log('Removing load marker for passenger:', event.data);
                        existingLoadMarker.remove();
                        this.visualManager.markers.load.delete(event.data);
                    } else {
                        console.log('No load marker found for passenger:', event.data);
                    }
                    
                    // Update passenger state
                    marker.passengers.delete(event.data);
                    this.processEvent({
                        type: 'UPDATE_PASSENGER',
                        passengerId: event.data,
                        newState: 'COMPLETED',
                        trikeId: marker.id,
                        passengers: marker.passengers
                    });
                    break;

                case "ENQUEUE":
                    // Create enqueue line between trike and passenger
                    const passengerMarker = this.visualManager.getMarker('appear', event.data);
                    if (passengerMarker) {
                        // Check if enqueue line already exists for this passenger
                        const existingLine = this.visualManager.markers.enqueueLines.get(event.data);
                        if (!existingLine) {
                            console.log(`Creating enqueue line for passenger ${event.data}`);
                            this.visualManager.createEnqueueLine(
                                marker.id,
                                event.data,
                                marker.getLatLng(),
                                passengerMarker.getLatLng()
                            );
                        } else {
                            console.log(`Enqueue line already exists for passenger ${event.data}`);
                        }
                    }
                    
                    this.processEvent({
                        type: 'UPDATE_PASSENGER',
                        passengerId: event.data,
                        newState: 'ENQUEUED',
                        trikeId: marker.id,
                        passengers: marker.passengers
                    });
                    break;
            }
            
            marker.currentEventIndex++;
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

    // Add method to check and process trike events every frame
    checkTrikeEvents(timestamp) {
        // console.log('checkTrikeEvents called with timestamp:', timestamp);
        
        // Get all trike markers
        const trikeMarkers = Array.from(this.visualManager.markers.trike.values());
        // console.log('Found trike markers:', trikeMarkers.length);
        
        trikeMarkers.forEach(marker => {
            // console.log('Checking events for trike:', marker.id);
            if (!marker.events || !Array.isArray(marker.events)) {
                // console.log('No events array for trike:', marker.id);
                return;
            }
            
            // console.log('Events for trike:', marker.id, marker.events);
            // console.log('Current event index:', marker.currentEventIndex);
            
            // Check all events that should occur at this timestamp
            while (marker.currentEventIndex < marker.events.length) {
                const event = marker.events[marker.currentEventIndex];
                if (!event) {
                    console.warn(`Invalid event at index ${marker.currentEventIndex} for marker ${marker.id}`);
                    marker.currentEventIndex++;
                    continue;
                }

                // console.log('Checking event:', event);
                // console.log('Event time:', event.time, 'Current timestamp:', timestamp);

                // Check if this event should be processed at this timestamp
                if (event.time === timestamp) {
                    // console.log(`Processing event for ${marker.id} at time ${timestamp}:`, event);
                    
                    // For LOAD and DROP-OFF events, log with trike ID
                    if (event.type === "LOAD" || event.type === "DROP-OFF") {
                        // console.log('Logging LOAD/DROP-OFF event with trike ID:', marker.id);
                        // Log the event with trike ID
                        this.visualManager.logEvent(
                            timestamp,
                            marker.id,  // Use trike ID
                            event.type,
                            event.data  // Use passenger ID as data
                        );
                    } else if (event.type === "APPEAR") {
                        // console.log('Logging APPEAR event for:', marker.id);
                        // Log appear events with the entity's ID
                        this.visualManager.logEvent(
                            timestamp,
                            marker.id,
                            event.type,
                            event.data
                        );
                    } else if (event.type !== "MOVE" && event.type !== "WAIT") {
                        // console.log('Logging other event:', event.type, 'for trike:', marker.id);
                        // Log other events (except MOVE and WAIT) with trike ID
                        this.visualManager.logEvent(
                            timestamp,
                            marker.id,
                            event.type,
                            event.data
                        );
                    }

                    // Then handle the event
                    this.handleEvent(marker, event);
                } else if (event.time > timestamp) {
                    // console.log('Event time is in the future, stopping processing');
                    // If we hit an event that's not for this frame, stop processing
                    break;
                } else {
                    // console.log('Skipping past event');
                    // Skip past events
                    marker.currentEventIndex++;
                }
            }
        });
    }
}

// Create and export the event processor instance
export const eventProcessor = new EventProcessor();

// Make event processor available globally
window.eventProcessor = eventProcessor; 