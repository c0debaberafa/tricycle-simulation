/*
    Visualizer

    This module is used to run a simple visualizer for the simulator. There's not much to modify
    here unless you want to make the visualizer prettier.
    
    NOTE: If your device can't handle the load, the simulator might look weird. Don't visualize
    heavy simulations.
*/

// L is imported from LeafletJS

function haversine(lat1, lon1, lat2, lon2) {
    // Returns distance in meters
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

let SIM_TIME = 0; 
const FRAME_DURATION_MS = 33;
const speedScale = 1000 / FRAME_DURATION_MS; // 10

let allMovingMarkers = []; // Store references to all moving markers

function simulationTick(){
    SIM_TIME += 1; // 1 frame per tick

    // Update all moving markers to current simulation time
    allMovingMarkers.forEach(marker => {
        marker.setSimTime(SIM_TIME * FRAME_DURATION_MS); // or just SIM_TIME if your plugin expects frames
    });

    // Check for events to show popups
    checkAndShowPopups(SIM_TIME);
    setTimeout(simulationTick, FRAME_DURATION_MS);
}

let pendingPopups = [];

function checkAndShowPopups(currentSimTime){
    // We'll keep events that are not yet triggered
    let stillPending = [];
    for (const event of pendingPopups) {
        if (event.type !== 'MOVE' && event.type !== 'WAIT' && event.location && event.time !== undefined) {
            // Find the related trike marker
            const trikeMarker = allMovingMarkers.find(m => m.id === event.trikeId);
            if (!trikeMarker) continue;

            // Get trike's current position
            const trikePos = trikeMarker.getLatLng();
            const [lng, lat] = event.location;

            // Check if sim time is right and trike is close to event location
            const dist = haversine(trikePos.lat, trikePos.lng, lat, lng);
            if (currentSimTime >= event.time && dist < 10) { // 10 meters threshold
                let message = `${event.trikeId} ${event.type} ${event.data ?? ""}`.trim();
                showEventMarker(lat, lng, message);
                // Don't keep this event
            } else {
                stillPending.push(event);
            }
        }
    }
    pendingPopups = stillPending;
}

function pointsToRaw(path) {
    // Convert [{type:..., data:[lng,lat]}, ...] to [[lat, lng], ...]
    return path.map(point => [point.data[1], point.data[0]]);
}

let map = L.map('map').setView([14.6436,121.0572], 17); // NOTE: modify to show simulation area

L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
}).addTo(map);

function showEventMarker(lat, lng, message) {
    const marker = L.marker([lat, lng], {
        icon: L.divIcon({
            className: 'red-marker',
            html: '<div style="background-color: red; width: 8px; height: 8px; border-radius: 50%;"></div>'
        })
    })
        .addTo(map)
        .bindTooltip(message, { permanent: true, direction: 'top' });

    return marker;
}

async function show_real(id, t, p) {

    // Retrieve simulation data
    const api = `http://localhost:5050/real/${id}/${t}/${p}`
    const { trikes, passengers } = await fetch(api).then(res => res.json());

    // Tricycle marker loop
    for(let i=0; i<trikes.length; i++) {
        const trike = trikes[i];
        // Scale speed to match frame duration
        const degreesPerMs = (trike.speed * speedScale) / 111000 / 1000;
        let trike_marker = L.Marker.movingMarker(
            trike.id,
            pointsToRaw(trike.path),
            trike.createTime,
            Infinity,
            degreesPerMs,
            trike.events
        );
        allMovingMarkers.push(trike_marker);
        trike_marker.addTo(map);
    }

    // Passenger marker loop
    for(let i=0; i<passengers.length; i++) {
        const passenger = passengers[i];
        passenger_marker = L.Marker.movingMarker(
            passenger.id,
            pointsToRaw(passenger.path), 
            passenger.createTime, 
            passenger.deathTime !== -1 ? passenger.deathTime/10 : Infinity, 
            0
        );
        passenger_marker.start()
    }

    trikes.forEach(trike => {
        if (trike.events) {
            trike.events.forEach(event => {
                if (event.type !== 'MOVE' && event.type !== 'WAIT' && event.location && event.time !== undefined) {
                    event.trikeId = trike.id; // Attach trike id for message
                    pendingPopups.push(event);
                }
            });
        }
    });
    pendingPopups.sort((a, b) => a.time - b.time);

    simulationTick();
}

// use the ID of the run you want to visualize
// run ID, num trikes, num passengers
show_real("3-4-10-ehpbvmilmwsn", 3, 10)

// /home/c0debaberafa/codebase/generator/data/real/3-4-10-ehpbvmilmwsn

