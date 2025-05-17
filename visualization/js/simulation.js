/**
 * Simulation State and Control Module
 * 
 * This module manages the simulation state and control logic.
 */

// ===== Constants and Configuration =====
const FRAME_DURATION_MS = 16.67;  // 60 FPS for smoother animation
const SPEED_MULTIPLIER = 1.0;  // Reset to 1.0 since speed is now handled in moving_marker.js

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

// Initialize global time
window.GLOBAL_TIME_MS = 0;

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
 * Main simulation tick function - updates positions and checks events
 */
function simulationTick() {
    SIM_TIME += 1; // Increment frame counter
    window.GLOBAL_TIME_MS += FRAME_DURATION_MS;
    
    console.log(`Simulation tick - Frame: ${SIM_TIME}`);

    // Update all moving markers to current simulation time
    allMovingMarkers.forEach(marker => {
        marker.setSimTime(window.GLOBAL_TIME_MS);
    });

    setTimeout(simulationTick, FRAME_DURATION_MS);
}

/**
 * Update passenger state in the simulation
 * @param {string} passengerId - ID of the passenger
 * @param {string} newState - New state to set
 */
function updatePassengerState(passengerId, newState) {
    // Remove from all states first
    Object.values(passengerStates).forEach(set => set.delete(passengerId));
    // Add to new state
    passengerStates[newState].add(passengerId);
    // Update the display immediately
    updatePassengerStatus();
}

/**
 * Update the passenger status display
 */
function updatePassengerStatus() {
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