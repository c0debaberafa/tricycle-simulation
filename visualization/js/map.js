/*
    Visualizer

    This module is used to run a simple visualizer for the simulator. There's not much to modify
    here unless you want to make the visualizer prettier.
    
    NOTE: If your device can't handle the load, the simulator might look weird. Don't visualize
    heavy simulations.
*/

// L is imported from LeafletJS

let map = L.map('map').setView([14.6436,121.0572], 17); // NOTE: modify to show simulation area

L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
}).addTo(map);

async function show_real(id, t, p) {
    const api = `http://localhost:5050/real/${id}/${t}/${p}`

    const { trikes, passengers } = await fetch(api).then(res => res.json());

    for(let i=0; i<trikes.length; i++) {
        const trike = trikes[i];
        trike_marker = L.Marker.movingMarker(
            trike.id,
            pointsToRaw(trike.path),
            trike.createTime,
            Infinity,
            trike.speed,
            trike.events
        );
        trike_marker.start()
    }
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
}

// use the ID of the run you want to visualize
show_real("6-1-100-netbueclmvuq", 5, 100)