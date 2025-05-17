/**
 * Marker Utilities Module
 * 
 * This module contains utility functions for creating different types of markers
 * used in the visualization.
 */

/**
 * Interpolate position between two points
 * @param {Array} p1 - First point [lat, lng]
 * @param {Array} p2 - Second point [lat, lng]
 * @param {number} progress - Progress between points (0 to 1)
 * @returns {Array} Interpolated position [lat, lng]
 */
function interpolatePosition(p1, p2, progress) {
    return [
        p1[0] + (p2[0] - p1[0]) * progress,
        p1[1] + (p2[1] - p1[1]) * progress
    ];
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