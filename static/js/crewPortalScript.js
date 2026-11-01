// Initialize Map (default view centered on Vulindlela area)
const map = L.map('crewMap', { zoomControl: true }).setView([-28.852392, 31.851507], 13);

// 1. High-Resolution Satellite Base Layer
const satelliteLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    minZoom: 3,
    maxZoom: 19,
    maxNativeZoom: 17,
    attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
});

// 2. Hybrid Labels & Roads Overlay Layer
const hybridLabels = L.tileLayer('https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}', {
    minZoom: 3,
    maxZoom: 19,
    maxNativeZoom: 17,
    attribution: 'Labels &copy; Esri'
});

satelliteLayer.addTo(map);
hybridLabels.addTo(map);

// --- Fullscreen Control ---
const fullscreenControl = L.control({ position: 'topright' });
fullscreenControl.onAdd = function (map) {
    const div = L.DomUtil.create('div', 'leaflet-bar leaflet-control');
    div.innerHTML = `<a href="#" id="fullscreenBtn" title="Toggle Fullscreen" style="font-size: 16px; line-height: 30px; text-align: center; text-decoration: none; color: #333; background: white; width: 30px; height: 30px; display: block; font-weight: bold;">⛶</a>`;
    
    div.onclick = function (e) {
        e.preventDefault();
        const mapContainer = document.getElementById('crewMap');
        const btn = document.getElementById('fullscreenBtn');
        
        mapContainer.classList.toggle('fullscreen-mode');
        
        if (mapContainer.classList.contains('fullscreen-mode')) {
            btn.innerHTML = '🗕';
            btn.title = 'Exit Fullscreen';
        } else {
            btn.innerHTML = '⛶';
            btn.title = 'Full Screen';
        }
        
        setTimeout(() => { map.invalidateSize(); }, 100);
    };
    return div;
};
fullscreenControl.addTo(map);

// Custom Truck Icon for Cleanup Crew
const truckIcon = L.divIcon({
    className: 'custom-truck-icon',
    html: '<div style="font-size: 24px; background: white; border-radius: 50%; padding: 2px; box-shadow: 0 2px 5px rgba(0,0,0,0.3); text-align: center;">🚚</div>',
    iconSize: [35, 35],
    iconAnchor: [17, 17]
});

// Helper function to broadcast coordinates to Flask backend
function broadcastCrewLocation(lat, lng) {
    fetch('/api/update-crew-location', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ latitude: lat, longitude: lng })
    }).catch(err => console.log("Broadcasting error:", err));
}

// Load tasks from Flask JSON element
const tasksDataElement = document.getElementById('tasks-data');
if (tasksDataElement) {
    const tasks = JSON.parse(tasksDataElement.textContent);
    
    const activeTask = tasks.find(task => task.latitude && task.longitude && task.status === "In Progress") 
                      || tasks.find(task => task.latitude && task.longitude && task.status !== "Resolved");

    if (activeTask) {
        const incidentLat = parseFloat(activeTask.latitude);
        const incidentLng = parseFloat(activeTask.longitude);

        // Add Incident Marker (Waste Site)
        L.marker([incidentLat, incidentLng])
            .addTo(map)
            .bindPopup(`<b>Incident Spot (${activeTask.report_id})</b><br>${activeTask.location}`)
            .openPopup();

        let truckMarker = null;
        let routingControl = null;
        let isLocationLocked = false; // Prevents GPS updates/resets once locked

        let selectedLat = null;
        let selectedLng = null;

        const lockBtn = document.getElementById('lockLocationBtn');
        const lockStatus = document.getElementById('lockStatus');

        function updateDriverMapAndRoute(lat, lng) {
            if (isLocationLocked) return; // Do nothing if location is locked

            selectedLat = lat;
            selectedLng = lng;

            // Broadcast to backend server so admin sees it too
            broadcastCrewLocation(lat, lng);

            if (!truckMarker) {
                truckMarker = L.marker([lat, lng], { icon: truckIcon })
                    .addTo(map)
                    .bindPopup(`<b>Your Location</b><br><i>Click map to adjust, then click 'Lock My Location'</i>`)
                    .openPopup();
            } else {
                truckMarker.setLatLng([lat, lng]);
            }

            if (!routingControl) {
                routingControl = L.Routing.control({
                    waypoints: [
                        L.latLng(lat, lng),       
                        L.latLng(incidentLat, incidentLng)  
                    ],
                    routeWhileDragging: false,
                    addWaypoints: false,
                    fitSelectedRoutes: true,
                    show: true,
                    createMarker: function() { return null; },
                    lineOptions: {
                        styles: [{color: '#28a745', opacity: 0.85, weight: 6}]
                    }
                }).addTo(map);
            } else {
                routingControl.setWaypoints([
                    L.latLng(lat, lng),
                    L.latLng(incidentLat, incidentLng)
                ]);
            }

            // Show lock button once coordinates are set
            if (lockBtn) lockBtn.style.display = 'inline-block';
        }

        // Initial geolocation lookup
        if ("geolocation" in navigator) {
            navigator.geolocation.getCurrentPosition(
                function(position) {
                    updateDriverMapAndRoute(position.coords.latitude, position.coords.longitude);
                },
                function(error) {
                    console.warn("Geolocation warning:", error.message);
                    updateDriverMapAndRoute(incidentLat - 0.005, incidentLng - 0.005);
                },
                { enableHighAccuracy: true, timeout: 5000, maximumAge: 0 }
            );
        } else {
            updateDriverMapAndRoute(incidentLat - 0.005, incidentLng - 0.005);
        }

        // Allow manual click-to-correct before locking
        map.on('click', function(e) {
            if (isLocationLocked) return;
            updateDriverMapAndRoute(e.latlng.lat, e.latlng.lng);
        });

        // Handle "Lock My Location" click event
        if (lockBtn) {
            lockBtn.addEventListener('click', function() {
                if (selectedLat && selectedLng) {
                    isLocationLocked = true; // Permanently lock session
                    lockBtn.style.display = 'none'; // Hide button
                    if (lockStatus) {
                        lockStatus.innerHTML = "Location Locked Successfully!";
                    }
                    if (truckMarker) {
                        truckMarker.bindPopup(`<b>Locked Crew Location</b><br><i>Position secured & synced</i>`).openPopup();
                    }
                    // Final confirmation sync to backend
                    broadcastCrewLocation(selectedLat, selectedLng);
                }
            });
        }

    } else {
        tasks.forEach(task => {
            if (task.latitude && task.longitude) {
                var markerColor = task.status === "Resolved" ? "green" : "red";
                L.circleMarker([task.latitude, task.longitude], {
                    color: markerColor,
                    fillColor: markerColor,
                    fillOpacity: 0.8,
                    radius: 9
                }).addTo(map).bindPopup("<b>" + task.report_id + "</b><br>Status: " + task.status);
            }
        });
    }
}

// Modal Controls
function openProofModal(reportId) {
    document.getElementById('modalReportId').value = reportId;
    const modal = document.getElementById('proofModal');
    modal.style.display = 'flex';
    modal.classList.add('active');
}

function closeProofModal() {
    const modal = document.getElementById('proofModal');
    modal.style.display = 'none';
    modal.classList.remove('active');
    document.getElementById('completion_photo').value = '';
    document.getElementById('submitProofBtn').style.display = 'none';
}

function handlePhotoSelection(event) {
    const file = event.target.files[0];
    const submitBtn = document.getElementById('submitProofBtn');
    const feedbackBox = document.getElementById('gpsFeedback');

    if (feedbackBox) {
        feedbackBox.style.display = 'none';
        feedbackBox.innerHTML = '';
    }

    if (file) {
        submitBtn.style.display = 'inline-block';
    } else {
        submitBtn.style.display = 'none';
    }
}