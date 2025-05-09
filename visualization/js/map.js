/*
 * Visualization Module
 * 
 * This module handles the visualization of the trike simulation, including:
 * - Map initialization and setup
 * - Trike and passenger movement
 * - Event visualization and logging
 * - Time synchronization between movement and events
 */

// ===== Constants and Configuration =====
const FRAME_DURATION_MS = 16.67;  // 60 FPS for smoother animation
const SPEED_MULTIPLIER = 5.0;  // Increase speed for better visualization

// ===== Global State =====
let SIM_TIME = 0;  // Current simulation frame
let allMovingMarkers = [];  // Store references to all moving markers
let tooltipStackCounter = {};  // Track stacked tooltips at same location
let passengerStates = {
    WAITING: new Set(),
    ENQUEUED: new Set(),
    ONBOARD: new Set(),
    COMPLETED: new Set()
};

// ===== Map Initialization =====
let map = L.map('map').setView([14.6436,121.0572], 17);

L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
}).addTo(map);

// ===== Utility Functions =====

/**
 * Calculate distance between two points using the Haversine formula
 * @param {number} lat1 - Latitude of first point
 * @param {number} lon1 - Longitude of first point
 * @param {number} lat2 - Latitude of second point
 * @param {number} lon2 - Longitude of second point
 * @returns {number} Distance in meters
 */
function haversine(lat1, lon1, lat2, lon2) {
    function toRad(x) { return x * Math.PI / 180; }
    const R = 6371000; // Earth radius in meters
    const dLat = toRad(lat2 - lat1);
    const dLon = toRad(lon2 - lon1);
    const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
              Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) *
              Math.sin(dLon/2) * Math.sin(dLon/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    return R * c;
}

/**
 * Convert path points to raw coordinates
 * @param {Array} path - Array of points with type and data
 * @returns {Array} Array of [lat, lng] coordinates
 */
function pointsToRaw(path) {
    return path.map(point => [point.data[1], point.data[0]]);
}

/**
 * Create a circular marker with specified color
 * @param {Array} latlng - [lat, lng] coordinates
 * @param {string} color - Color of the marker
 * @param {string} tooltip - Tooltip text
 * @returns {L.Marker} Leaflet marker
 */
function createCircleMarker(latlng, color, tooltip) {
    return L.marker(latlng, {
        icon: L.divIcon({
            className: 'circle-marker',
            html: `<div style="background-color: ${color}; width: 8px; height: 8px; border-radius: 50%;"></div>`
        })
    })
    .addTo(map)
    .bindTooltip(tooltip, {
        permanent: false,
        direction: 'top'
    });
}

/**
 * Create a square marker for terminals
 * @param {Array} latlng - [lat, lng] coordinates
 * @param {string} tooltip - Tooltip text
 * @returns {L.Marker} Leaflet marker
 */
function createTerminalMarker(latlng, tooltip) {
    return L.marker(latlng, {
        icon: L.divIcon({
            className: 'terminal-marker',
            html: `<div style="background-color: black; width: 12px; height: 12px;"></div>`
        })
    })
    .addTo(map)
    .bindTooltip(tooltip, {
        permanent: false,
        direction: 'top'
    });
}

/**
 * Create a square marker for roam endpoints
 * @param {Array} latlng - [lat, lng] coordinates
 * @param {string} tooltip - Tooltip text
 * @returns {L.Marker} Leaflet marker
 */
function createRoamEndpointMarker(latlng, tooltip) {
    return L.marker(latlng, {
        icon: L.divIcon({
            className: 'roam-endpoint-marker',
            html: `<div style="background-color: grey; width: 12px; height: 12px;"></div>`
        })
    })
    .addTo(map)
    .bindTooltip(tooltip, {
        permanent: false,
        direction: 'top'
    });
}

// ===== Simulation Control =====

/**
 * Main simulation tick function - updates positions and checks events
 */
function simulationTick() {
    SIM_TIME += 1; // Increment frame counter
    const timeInMs = SIM_TIME * FRAME_DURATION_MS;
    
    console.log(`Simulation tick - Frame: ${SIM_TIME}, Time: ${timeInMs}ms`);

    // Update all moving markers to current simulation time
    allMovingMarkers.forEach(marker => {
        marker.setSimTime(timeInMs);
    });

    setTimeout(simulationTick, FRAME_DURATION_MS);
}

// ===== Main Visualization Function =====

/**
 * Initialize and start the visualization
 * @param {string} id - Simulation run ID
 * @param {number} t - Number of trikes
 * @param {number} p - Number of passengers
 */
async function show_real(id, t, p) {
    console.log(`Loading simulation data for run ${id}`);
    
    // Reset passenger states
    passengerStates = {
        WAITING: new Set(),
        ENQUEUED: new Set(),
        ONBOARD: new Set(),
        COMPLETED: new Set()
    };

    // Retrieve simulation data
    const api = `http://localhost:5050/real/${id}/${t}/${p}`
    const { trikes, passengers } = await fetch(api).then(res => res.json());

    // Initialize all passengers as WAITING
    passengers.forEach(passenger => {
        passengerStates.WAITING.add(passenger.id);
    });
    updatePassengerStatus();

    // Clear existing visualization
    allMovingMarkers.forEach(marker => marker.remove());
    allMovingMarkers = [];

    // Load and display terminal data
    console.log('Loading terminal data...');
    try {
        const terminalsUrl = `http://localhost:5050/real/${id}/terminals.json`;
        console.log(`Fetching terminal data from: ${terminalsUrl}`);
        const terminalsResponse = await fetch(terminalsUrl);
        if (!terminalsResponse.ok) {
            throw new Error(`HTTP error! status: ${terminalsResponse.status}`);
        }
        const terminals = await terminalsResponse.json();
        console.log('Loaded terminals:', terminals);
        terminals.forEach(terminal => {
            createTerminalMarker(
                [terminal.location[1], terminal.location[0]], // Convert [x,y] to [lat,lng]
                `Terminal ${terminal.id}: ${terminal.remaining_passengers} passengers, ${terminal.remaining_tricycles} tricycles`
            );
        });
    } catch (error) {
        console.error('Failed to load terminals:', error);
    }

    // Load and display roam endpoints
    console.log('Loading roam endpoints...');
    try {
        const roamUrl = `http://localhost:5050/real/${id}/roam_endpoints.json`;
        console.log(`Fetching roam endpoints from: ${roamUrl}`);
        const roamResponse = await fetch(roamUrl);
        if (!roamResponse.ok) {
            throw new Error(`HTTP error! status: ${roamResponse.status}`);
        }
        const roamEndpoints = await roamResponse.json();
        console.log('Loaded roam endpoints:', roamEndpoints);
        roamEndpoints.forEach(endpoint => {
            // Log the raw endpoint data
            console.log('Processing roam endpoint:', endpoint);
            
            // Create marker for start point
            const startLatlng = [endpoint.start_point[1], endpoint.start_point[0]];
            console.log('Start point coordinates:', startLatlng);
            createRoamEndpointMarker(
                startLatlng,
                `Roam Start: ${endpoint.tricycle_id}`
            );

            // Create marker for end point
            const endLatlng = [endpoint.end_point[1], endpoint.end_point[0]];
            console.log('End point coordinates:', endLatlng);
            createRoamEndpointMarker(
                endLatlng,
                `Roam End: ${endpoint.tricycle_id}`
            );
        });
    } catch (error) {
        console.error('Failed to load roam endpoints:', error);
    }

    // Initialize trike markers
    for(let i=0; i<trikes.length; i++) {
        const trike = trikes[i];
        // Use raw speed with multiplier for better visualization
        const degreesPerMs = (trike.speed * SPEED_MULTIPLIER) / 111000 / 1000;
        console.log(`Creating trike ${trike.id} with speed ${degreesPerMs} degrees/ms`);
        
        let trike_marker = L.Marker.movingMarker(
            trike.id,
            pointsToRaw(trike.path),
            trike.createTime * FRAME_DURATION_MS,
            Infinity,
            degreesPerMs,
            trike.events
        );
        allMovingMarkers.push(trike_marker);
        trike_marker.addTo(map);
        trike_marker.start(); // Make sure to start the marker
    }

    // Initialize passenger markers
    for(let i=0; i<passengers.length; i++) {
        const passenger = passengers[i];
        // Create a marker that only shows events, no movement
        const passenger_marker = L.Marker.movingMarker(
            passenger.id,
            [[passenger.src[1], passenger.src[0]]], // Convert [x,y] to [lat,lng] format
            passenger.createTime * FRAME_DURATION_MS,
            passenger.deathTime !== -1 ? passenger.deathTime * FRAME_DURATION_MS : Infinity,
            0,
            passenger.events
        );
        // Don't add the marker to the map, just start it to process events
        passenger_marker.start();
    }

    // Start simulation
    simulationTick();
}

function updatePassengerStatus() {
    let statusDiv = document.getElementById('passengerStatus');
    if (!statusDiv) {
        // Create the status div if it doesn't exist
        statusDiv = document.createElement('div');
        statusDiv.id = 'passengerStatus';
        statusDiv.style.position = 'absolute';
        statusDiv.style.right = '20px';
        statusDiv.style.top = '20px';
        statusDiv.style.backgroundColor = 'white';
        statusDiv.style.padding = '10px';
        statusDiv.style.border = '1px solid #ccc';
        statusDiv.style.borderRadius = '5px';
        statusDiv.style.fontFamily = 'monospace';
        statusDiv.style.zIndex = '1000';
        statusDiv.style.whiteSpace = 'pre';
        document.body.appendChild(statusDiv);
    }

    // Format passenger numbers (remove 'passenger_' prefix and sort numerically)
    const formatPassengers = (set) => Array.from(set)
        .map(id => id.replace('passenger_', ''))
        .sort((a, b) => parseInt(a) - parseInt(b))
        .join(' ');

    const content = `PASSENGER STATUS
===============
WAITING: ${formatPassengers(passengerStates.WAITING)}
ENQUEUED: ${formatPassengers(passengerStates.ENQUEUED)}
ONBOARD: ${formatPassengers(passengerStates.ONBOARD)}
COMPLETED: ${formatPassengers(passengerStates.COMPLETED)}`;
    statusDiv.textContent = content;
}

function updatePassengerState(passengerId, newState) {
    // Remove from all states first
    Object.values(passengerStates).forEach(set => set.delete(passengerId));
    // Add to new state
    passengerStates[newState].add(passengerId);
    // Update the display immediately
    updatePassengerStatus();
}

// use the ID of the run you want to visualize
// run ID, num trikes, num passengers
show_real("3-2-20-nfamihevxzbo", 3, 20)

// /3-2-20-omceyaycyqmn 3-2-20-mybbizldhghs

