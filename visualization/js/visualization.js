/**
 * Visualization Orchestration Module
 * 
 * This module handles the main visualization logic and data loading.
 */

// Initialize tab switching functionality
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

    // Start the visualization with default values
    show_real("3-2-20-mwmfnjlaeogv", 3, 20);
});

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
            // Calculate speed in degrees per millisecond
            // Convert m/s to degrees/ms using a more accurate conversion
            // 1 degree of latitude ≈ 111km, 1 degree of longitude ≈ 111km * cos(latitude)
            const lat = pointsToRaw(trike.path)[0][0]; // Get latitude from first point
            const degreesPerMs = trike.speed * 50 / (111000 * Math.cos(lat * Math.PI / 180)) / 1000;
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

/**
 * Convert path points to raw coordinates
 * @param {Array} path - Array of points with type and data
 * @returns {Array} Array of [lat, lng] coordinates
 */
function pointsToRaw(path) {
    return path.map(point => [point.data[1], point.data[0]]);
} 