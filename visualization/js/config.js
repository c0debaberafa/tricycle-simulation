/**
 * Configuration Module
 * 
 * This module contains all configuration constants used across the visualization system.
 */

// Simulation timing
export const TIMING_CONFIG = {
    frameDuration: 16,  // Target frame duration in ms (~60fps)
    simulationFrameTime: 10,  // Time between simulation updates in ms
    baseSpeedMultiplier: 2000  // Base speed multiplier for visualization
};

// Map configuration
export const MAP_CONFIG = {
    center: [14.6436, 121.0572],
    zoom: 17,
    maxZoom: 19,
    tileLayer: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
};

// API endpoints
export const API_ENDPOINTS = {
    simulation: (id, t, p) => `http://localhost:5050/real/${id}/${t}/${p}`,
    terminals: (id) => `http://localhost:5052/real/${id}/terminals.json`
};

// Default simulation parameters
export const DEFAULT_SIMULATION = {
    id: "15-2-100-icmbauqodozx",
    trikes: 15,
    passengers: 100
};

// Utility functions
export function isValidCoordinates(coords) {
    // Handle point object format
    if (coords && typeof coords === 'object' && coords.type === 'point' && Array.isArray(coords.data)) {
        return isValidCoordinates(coords.data);
    }
    
    // Handle array format
    return Array.isArray(coords) && 
           coords.length === 2 && 
           typeof coords[0] === 'number' && 
           typeof coords[1] === 'number' &&
           !isNaN(coords[0]) && 
           !isNaN(coords[1]) &&
           coords[0] !== undefined && 
           coords[1] !== undefined;
}

export function getEuclideanDistance(point1, point2) {
    // Handle point object format
    const p1 = point1.type === 'point' ? point1.data : point1;
    const p2 = point2.type === 'point' ? point2.data : point2;
    
    return Math.sqrt(
        Math.pow(p2[0] - p1[0], 2) + 
        Math.pow(p2[1] - p1[1], 2)
    );
} 