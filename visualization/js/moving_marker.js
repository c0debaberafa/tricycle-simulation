/**
 * Moving Marker Implementation for Leaflet
 * 
 * This module extends Leaflet's Marker class to support animated movement
 * along paths with visual management integration.
 */

import { TIMING_CONFIG } from './config.js';

// Use the REFRESH_TIME from managers.js if available, otherwise define it
const MARKER_REFRESH_TIME = window.REFRESH_TIME || TIMING_CONFIG.frameDuration; // ms between updates

// Constants for coordinate calculations
const SIMULATION_FRAME_TIME = TIMING_CONFIG.simulationFrameTime; // Reduced from 100ms to 50ms for faster updates

// Global state
window.CURRENT_FRAME = 0;
window.GLOBAL_TIME_MS = 0;
window.SIMULATION_SPEED = 1; // Base simulation speed multiplier
window.INITIALIZED_TRIKES = new Set();

/**
 * Utility Functions
 */

/**
 * Returns the point between the source point and the destination point at
 * the percentage part of the segment connecting them.
 * 
 * @param {[number, number]} p1 Source Point [lng, lat] (OSRM format)
 * @param {[number, number]} p2 Destination Point [lng, lat] (OSRM format)
 * @param {number} prog Percentage travelled (0-1)
 * @returns {[number, number]} Interpolated point [lng, lat] (OSRM format)
 */
function interpolatePosition(p1, p2, prog) {
    return [p1[0] + prog * (p2[0] - p1[0]), p1[1] + prog * (p2[1] - p1[1])];
}

/**
 * Computes the euclidean distance between two points in degrees.
 * 
 * @param {[number, number]} p1 Point 1 [lng, lat] (OSRM format)
 * @param {[number, number]} p2 Point 2 [lng, lat] (OSRM format)
 * @returns {number} Distance in degrees
 */
function getEuclideanDistance(p1, p2) {
    return Math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2);
}

/**
 * Rounds a number to specified decimal places
 * 
 * @param {number} x Number to round
 * @param {number} places Number of decimal places
 * @returns {number} Rounded number
 */
function roundPlaces(x, places) {
    return Math.round(x * (10**places)) / (10**places);
}

L.MovingMarker = L.Marker.extend({
    /**
     * Initialize a new moving marker
     * 
     * @param {string} id Unique identifier for the marker
     * @param {Array} path Array of coordinates defining the marker's path
     * @param {number} stime Start time of the animation
     * @param {number} dtime Duration of the animation
     * @param {number} speed Speed of movement
     * @param {Array} events Array of events to process during animation
     */
    initialize: function (id, path, stime, dtime, speed, events) {
        // Check if this trike is already initialized
        if (window.INITIALIZED_TRIKES.has(id)) {
            console.log(`Trike ${id} already initialized, skipping`);
            return;
        }
        
        console.log(`Initializing marker ${id} with path:`, path);
        console.log('Events data:', events);
        
        // Only proceed with marker creation for trikes
        if (!id.startsWith("trike")) {
            console.log(`Skipping marker creation for non-trike ${id}`);
            return;
        }

        // Initialize properties
        this.id = id;
        this.speed = speed;
        this.path = this._validateAndProcessPath(path);
        this.stime = stime;
        this.dtime = dtime;
        this.events = events;
        this.passengers = new Set();
        this.currentPathIndex = 0;
        this.currentEventIndex = 0;
        this.status = 0; // Default status (IDLE)
        this._startTime = 0;
        this._animationFrame = null;
        this._currentPosition = null;
        this._isAnimating = false;
        this._lastSimulationFrame = -1; // Initialize frame tracking

        // Initialize base marker with custom icon
        if (this.path.length > 0) {
            // Convert OSRM [lng, lat] to Leaflet [lat, lng] for initial position
            const initialPos = [this.path[0][1], this.path[0][0]];
            console.log(`Initializing base marker ${id} at position:`, initialPos);
            L.Marker.prototype.initialize.call(this, initialPos);
            this._initializeMarker();
            this._currentPosition = this.path[0]; // Store in OSRM format
            
            // Mark as initialized
            window.INITIALIZED_TRIKES.add(id);
        } else {
            console.error(`No valid path points for marker ${id} initialization`);
        }
    },

    _validateAndProcessPath: function(path) {
        if (!Array.isArray(path) || path.length === 0) {
            console.error(`Invalid path for marker ${this.id}:`, path);
            return [];
        }

        return path.map((coord, index) => {
            let lng, lat;
            
            if (Array.isArray(coord)) {
                // Path should already be in [lng, lat] format from event processor
                [lng, lat] = coord;
            } else if (coord?.type === 'point' && Array.isArray(coord.data)) {
                // OSRM point format
                [lng, lat] = coord.data;
            } else {
                console.error(`Invalid coordinate format at index ${index} for marker ${this.id}:`, coord);
                return null;
            }

            if (typeof lat !== 'number' || typeof lng !== 'number' || isNaN(lat) || isNaN(lng)) {
                console.error(`Invalid coordinate values at index ${index} for marker ${this.id}:`, coord);
                return null;
            }

            // Keep coordinates in OSRM format [lng, lat]
            return [lng, lat];
        }).filter(coord => coord !== null);
    },

    _initializeMarker: function() {
        // Create marker with custom icon
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
        this.setIcon(markerIcon);

        // Add to visual manager
        if (window.visualManager) {
            window.visualManager.addMarker('trike', this.id, this);
            // Set initial color using updateTrikeColor
            window.visualManager.updateTrikeColor(this, 'DEFAULT');
        }
    },

    _startAnimation: function() {
        // Only start animation if not already running and properly initialized
        if (this._isAnimating || !window.INITIALIZED_TRIKES.has(this.id)) {
            console.log(`Cannot start animation for ${this.id}: ${this._isAnimating ? 'already running' : 'not initialized'}`);
            return;
        }
        
        console.log(`Starting animation for ${this.id} with path length ${this.path.length}`);
        this._isAnimating = true;
        this._startTime = window.GLOBAL_TIME_MS;
        this._animate();
    },

    _animate: function() {
        // Skip animation if paused
        if (window.IS_PAUSED) {
            this._animationFrame = requestAnimationFrame(() => this._animate());
            return;
        }
        
        // Use the global frame counter
        const currentSimulationFrame = window.CURRENT_FRAME;
        
        // Only process new simulation frames and ensure we don't skip frames
        if (currentSimulationFrame > this._lastSimulationFrame) {
            // Calculate how many frames we need to process
            const framesToProcess = currentSimulationFrame - this._lastSimulationFrame;
            
            // Process each frame to maintain synchronization
            for (let i = 0; i < framesToProcess; i++) {
                // If we've reached the end of the path, stop moving
                if (this.currentPathIndex >= this.path.length - 1) {
                    console.log(`Trike ${this.id} reached end of path at index ${this.currentPathIndex}`);
                    this._isAnimating = false;
                    return;
                }
                
                // Get current position from path
                const currentPoint = this.path[this.currentPathIndex];
                
                // Set the position
                if (this._isValidCoordinate(currentPoint)) {
                    // Convert OSRM [lng, lat] to Leaflet [lat, lng] for display
                    const leafletPosition = [currentPoint[1], currentPoint[0]];
                    this.setLatLng(leafletPosition);
                    this._currentPosition = currentPoint;
                    
                    // Update visual elements
                    if (window.visualManager) {
                        // Update trike position with current path index first
                        window.visualManager.updateTrikePosition(this.id, leafletPosition, this.currentPathIndex);
                        
                        // Only update enqueue lines after the trike has moved
                        const enqueueLines = window.visualManager.markers.enqueueLines;
                        if (enqueueLines.size > 0) {
                            window.visualManager.updateEnqueueLines(this.id, this.getLatLng());
                        }
                        
                        window.visualManager.updateTrikeTooltip(this, this.id, this.passengers);
                    }
                    
                    // Move to next point
                    this.currentPathIndex++;
                } else {
                    console.error(`Invalid coordinate for trike ${this.id} at index ${this.currentPathIndex}:`, currentPoint);
                    this._isAnimating = false;
                    return;
                }
            }
            
            this._lastSimulationFrame = currentSimulationFrame;
        }
        
        // Continue animation
        this._animationFrame = requestAnimationFrame(() => this._animate());
    },

    _getTotalPathDistance: function() {
        let total = 0;
        for (let i = 0; i < this.path.length - 1; i++) {
            total += getEuclideanDistance(this.path[i], this.path[i + 1]);
        }
        return total;
    },

    _isValidCoordinate: function(coord) {
        return Array.isArray(coord) && 
               coord.length === 2 && 
               typeof coord[0] === 'number' && 
               typeof coord[1] === 'number' &&
               !isNaN(coord[0]) && 
               !isNaN(coord[1]);
    },

    /**
     * Event Processing Methods
     */

    _processEvents: function(timestamp) {
        if (!this.events || !Array.isArray(this.events)) return;

        while (this.currentEventIndex < this.events.length) {
            const event = this.events[this.currentEventIndex];
            if (!event) {
                console.warn(`Invalid event at index ${this.currentEventIndex} for marker ${this.id}`);
                this.currentEventIndex++;
                continue;
            }

            const shouldProcess = eventProcessor.processEvent({
                type: 'CHECK_EVENT_TIMING',
                event: event,
                currentTime: timestamp
            });

            if (!shouldProcess) break;

            if (stateManager.isValidEvent(event)) {
                eventProcessor.processEvent({
                    type: 'PROCESS_MARKER_EVENT',
                    marker: this,
                    event: event,
                    timestamp: timestamp
                });
            } else {
                console.warn(`Invalid event data for ${this.id}:`, event);
            }

            this.currentEventIndex++;
        }
    },

    /**
     * Event Handler Methods
     */

    createEventMarker: function(lat, lng, message) {
        const marker = eventProcessor.processEvent({
            type: 'CREATE_EVENT_MARKER',
            lat: lat,
            lng: lng,
            message: message,
            id: this.id
        });

        if (marker) {
            eventProcessor.processEvent({
                type: 'TRACK_EVENT_MARKER',
                marker: marker
            });
        }

        return marker;
    },

    logEvent: function(time, type, data) {
        eventProcessor.processEvent({
            type: 'LOG_EVENT',
            time: time,
            id: this.id,
            type: type,
            data: data
        });
    },

    // Public methods for external control
    updateStatus: function(status) {
        this.status = status;
        if (window.visualManager) {
            window.visualManager.updateTrikeColor(this, status);
            // Clean up enqueue lines when status changes from ENQUEUING
            if (this.status !== 5) { // 5 is ENQUEUING status
                window.visualManager.cleanupTrikeEnqueueLines(this.id);
            }
        }
    },

    updatePassengers: function(passengers) {
        this.passengers = new Set(passengers);
        if (window.visualManager) {
            window.visualManager.updateTrikeTooltip(this, this.id, this.passengers);
        }
    },

    setRoamPath: function(path) {
        if (window.visualManager) {
            window.visualManager.setRoamPath(this.id, path);
        }
    }
});

L.movingMarker = function (id, path, stime=0, dtime=Infinity, speed=0.1, events=null) {
    return new L.MovingMarker(id, path, stime, dtime, speed, events);
};

// Add a method to control simulation speed
L.MovingMarker.setSimulationSpeed = function(speed) {
    window.SIMULATION_SPEED = speed;
};