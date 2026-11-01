document.addEventListener("DOMContentLoaded", function () {
    const container = document.getElementById("mapContainer");
    const incidentLat = parseFloat(container.dataset.lat);
    const incidentLng = parseFloat(container.dataset.lng);
    const reportId = container.dataset.reportId;
    const incidentLocationName = container.dataset.location;
    const assignedCrewName = container.dataset.crew;

    // Initialize Map centered on incident spot
    const map = L.map('map').setView([incidentLat, incidentLng], 14);

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

    // Incident Spot Marker (Blue Pin - Waste Site)
    const incidentLatLng = L.latLng(incidentLat, incidentLng);
    L.marker(incidentLatLng).addTo(map)
        .bindPopup(`<b>Incident Spot (${reportId})</b><br>${incidentLocationName}`)
        .openPopup();

    // Custom Truck Icon for Cleanup Crew
    const truckIcon = L.divIcon({
        className: 'custom-truck-icon',
        html: '<div style="font-size: 24px; background: white; border-radius: 50%; padding: 2px; box-shadow: 0 2px 5px rgba(0,0,0,0.3); text-align: center;">🚚</div>',
        iconSize: [35, 35],
        iconAnchor: [17, 17]
    });

    let crewMarker = null;
    let routingControl = null;
    let lastLat = null;
    let lastLng = null;

    // Function to fetch driver position from backend and sync admin map
    function updateAdminTrackingMap() {
        fetch('/api/get-crew-location')
            .then(res => res.json())
            .then(data => {
                if (data.latitude && data.longitude) {
                    if (data.latitude === lastLat && data.longitude === lastLng) return;

                    lastLat = data.latitude;
                    lastLng = data.longitude;
                    const crewLatLng = L.latLng(data.latitude, data.longitude);

                    // Update or create driver truck marker
                    if (!crewMarker) {
                        crewMarker = L.marker(crewLatLng, { icon: truckIcon })
                            .addTo(map)
                            .bindPopup(`<b>Cleanup Crew: ${assignedCrewName}</b><br>En route to incident`);
                    } else {
                        crewMarker.setLatLng(crewLatLng);
                    }

                    // Draw/Update route identically to driver view
                    if (!routingControl) {
                        routingControl = L.Routing.control({
                            waypoints: [
                                crewLatLng,
                                incidentLatLng
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
                            crewLatLng,
                            incidentLatLng
                        ]);
                    }
                }
            })
            .catch(err => console.log("Polling error:", err));
    }

    // Run immediately on page load
    updateAdminTrackingMap();

    // Poll backend every 3 seconds for live sync (just like Uber tracking)
    setInterval(updateAdminTrackingMap, 3000);
});