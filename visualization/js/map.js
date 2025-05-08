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
    // Retrieve simulation data
    const api = `http://localhost:5050/real/${id}/${t}/${p}`
    const { trikes, passengers } = await fetch(api).then(res => res.json());

    // Clear existing visualization
    allMovingMarkers.forEach(marker => marker.remove());
    allMovingMarkers = [];

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

// use the ID of the run you want to visualize
// run ID, num trikes, num passengers
show_real("3-2-20-qrzmaciukogo", 3, 20)

// / 3-1-20-derpniusjjsm

