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
const SPEED_MULTIPLIER = 40.0;  // Increased from 5.0 to 40.0 for 8x speed

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

// Wait for DOM to be fully loaded before initializing map
document.addEventListener('DOMContentLoaded', function() {
    // ===== Map Initialization =====
    console.log('Initializing map...');
    let map = L.map('map').setView([14.6436,121.0572], 17);
    console.log('Map initialized:', map);

    // Use CartoDB dark theme
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
    }).addTo(map);
    console.log('Tile layer added to map');

    // Make map available globally
    window.map = map;
});

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
    
    console.log(`Simulation tick - Frame: ${SIM_TIME}`);

    // Update all moving markers to current simulation time
    allMovingMarkers.forEach(marker => {
        marker.setSimTime(GLOBAL_TIME_MS);
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
    
    try {
        // Reset passenger states
        passengerStates = {
            WAITING: new Set(),
            ENQUEUED: new Set(),
            ONBOARD: new Set(),
            COMPLETED: new Set()
        };

        // Retrieve simulation data
        const api = `http://localhost:5051/real/${id}/${t}/${p}`
        console.log('Fetching data from:', api);
        const response = await fetch(api);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const { trikes, passengers } = await response.json();
        console.log('Received data:', { trikes, passengers });

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
    } catch (error) {
        console.error('Error in show_real:', error);
    }
}

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

function updatePassengerState(passengerId, newState) {
    // Remove from all states first
    Object.values(passengerStates).forEach(set => set.delete(passengerId));
    // Add to new state
    passengerStates[newState].add(passengerId);
    // Update the display immediately
    updatePassengerStatus();
}

// Tab switching functionality
document.addEventListener('DOMContentLoaded', function() {
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabPanes = document.querySelectorAll('.tab-pane');

    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            // Remove active class from all buttons and panes
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabPanes.forEach(pane => pane.classList.remove('active'));

            // Add active class to clicked button and corresponding pane
            button.classList.add('active');
            const tabId = button.getAttribute('data-tab');
            document.getElementById(tabId).classList.add('active');
        });
    });
});

// use the ID of the run you want to visualize
// run ID, num trikes, num passengers
// /show_real("3-2-20-mwmfnjlaeogv", 3, 20)

// /3-2-20-omceyaycyqmn 3-2-20-mybbizldhghs
// generator/data/real/3-2-20-yxjmsvodgtww

// Start the visualization
show_real("3-2-20-mwmfnjlaeogv", 3, 20);

