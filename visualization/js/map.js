/*
 * Main Visualization Module
 * 
 * This module serves as the main entry point for the visualization system.
 * It handles:
 * - Map initialization and setup
 * - Loading and processing simulation data
 * - Coordinating between managers
 * - Managing the simulation timing
 */

import { 
    TIMING_CONFIG,
    MAP_CONFIG, 
    API_ENDPOINTS,
    DEFAULT_SIMULATION 
} from './config.js';

import { stateManager, visualManager } from './managers.js';
import { eventProcessor } from './event_processor.js';

// ===== Map Initialization =====
export function initializeMap() {
    console.log('Initializing map...');
    const map = L.map('map').setView(MAP_CONFIG.center, MAP_CONFIG.zoom);

    // Use CartoDB dark theme
    L.tileLayer(MAP_CONFIG.tileLayer, {
        maxZoom: MAP_CONFIG.maxZoom,
        attribution: MAP_CONFIG.attribution
    }).addTo(map);

    // Make map available globally
    window.map = map;
    return map;
}

// ===== Simulation Control =====
function initializeSimulation() {
    // Reset state using StateManager
    stateManager.reset();
    window.GLOBAL_TIME_MS = 0;
    window.SIMULATION_SPEED = 1.0;
    window.IS_PAUSED = false;
    
    // Make managers available globally
    window.visualManager = visualManager;
    window.stateManager = stateManager;
    window.eventProcessor = eventProcessor;
    
    // Clear existing visualization using VisualManager
    visualManager.clearAllMarkers();

    // Add play/pause button
    const controlButton = L.control({ position: 'bottomright' });
    controlButton.onAdd = function() {
        const div = L.DomUtil.create('div', 'leaflet-control leaflet-bar');
        div.innerHTML = `
            <a href="#" title="Play/Pause" style="
                width: 30px;
                height: 30px;
                line-height: 30px;
                text-align: center;
                display: block;
                text-decoration: none;
                color: black;
                background: white;
                font-size: 18px;
                position: relative;
                z-index: 1001;
                margin-bottom: 220px;
            ">▶</a>
        `;
        div.onclick = function(e) {
            e.preventDefault();
            window.IS_PAUSED = !window.IS_PAUSED;
            div.querySelector('a').textContent = window.IS_PAUSED ? '▶' : '⏸';
        };
        return div;
    };
    controlButton.addTo(window.map);
}

function simulationTick() {
    // Skip if paused
    if (window.IS_PAUSED) {
        requestAnimationFrame(() => {
            setTimeout(simulationTick, TIMING_CONFIG.frameDuration);
        });
        return;
    }

    // Update simulation time and frame counter
    window.GLOBAL_TIME_MS += TIMING_CONFIG.frameDuration;
    window.CURRENT_FRAME = Math.floor(window.GLOBAL_TIME_MS / TIMING_CONFIG.simulationFrameTime);
    
    // Get current path index from state manager
    const currentFrame = stateManager.getMaxPathIndex();
    
    // Update frame counter
    visualManager.updateFrameCounter(currentFrame);
    
    // Check and process trike events for this frame
    if (window.eventProcessor) {
        window.eventProcessor.checkTrikeEvents(currentFrame);
    }
    
    // Use requestAnimationFrame for smoother animation
    requestAnimationFrame(() => {
        setTimeout(simulationTick, TIMING_CONFIG.frameDuration);
    });
}

// ===== Data Loading =====
async function loadSimulationData(id, t, p) {
    const response = await fetch(API_ENDPOINTS.simulation(id, t, p));
    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }
    return await response.json();
}

async function loadTerminalData(id) {
    const response = await fetch(API_ENDPOINTS.terminals(id));
    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }
    return await response.json();
}

// ===== Main Visualization Function =====
export async function show_real(id, t, p) {
    try {
        // Initialize simulation state
        initializeSimulation();

        // Load simulation data
        const { trikes, passengers } = await loadSimulationData(id, t, p);
        console.log('Raw passenger data:', passengers[0]); // Log first passenger for debugging

        // Process all initialization events
        eventProcessor.processEvent({
            type: 'INITIALIZE_SIMULATION',
            data: {
                passengers: passengers.map(p => {
                    console.log('Processing passenger:', p.id, 'src:', p.src); // Log each passenger's source
                    return {
                        id: p.id,
                        src: p.src,
                        createTime: p.createTime * TIMING_CONFIG.frameDuration,
                        deathTime: p.deathTime !== -1 ? p.deathTime * TIMING_CONFIG.frameDuration : Infinity,
                        events: p.events
                    };
                }),
                trikes: trikes.map(t => ({
                    id: t.id,
                    path: t.path.map(point => [point.data[1], point.data[0]]),
                    speed: (t.speed * TIMING_CONFIG.baseSpeedMultiplier) / 111000 / 1000,
                    createTime: t.createTime * TIMING_CONFIG.frameDuration,
                    events: t.events
                }))
            }
        });

        // Load and initialize terminals
        try {
            const terminals = await loadTerminalData(id);
            eventProcessor.processEvent({
                type: 'INITIALIZE_TERMINALS',
                data: terminals.map(t => ({
                    id: t.id,
                    location: [t.location[1], t.location[0]],
                    remaining_passengers: t.remaining_passengers,
                    remaining_tricycles: t.remaining_tricycles
                }))
            });
        } catch (error) {
            console.error('Failed to load terminals:', error);
        }

        // Start simulation
        simulationTick();
    } catch (error) {
        console.error('Error in show_real:', error);
    }
}

// ===== UI Initialization =====
function initializeUI() {
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabPanes = document.querySelectorAll('.tab-pane');

    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabPanes.forEach(pane => pane.classList.remove('active'));

            button.classList.add('active');
            const tabId = button.getAttribute('data-tab');
            document.getElementById(tabId).classList.add('active');
        });
    });
}

// use the ID of the run you want to visualize
// run ID, num trikes, num passengers
// /show_real("3-2-20-mwmfnjlaeogv", 3, 20)

// /3-2-20-omceyaycyqmn 3-2-20-mybbizldhghs
// generator/data/real/3-2-20-yxjmsvodgtww

// Initialize everything when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    initializeUI();
    show_real(DEFAULT_SIMULATION.id, DEFAULT_SIMULATION.trikes, DEFAULT_SIMULATION.passengers);
});

