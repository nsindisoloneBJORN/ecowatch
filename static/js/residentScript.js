let map;
let currentMarker = null;

// Tighter boundary box hard-focused strictly around KwaDlangezwa & UNIZULU
const southWest = L.latLng(-28.9200, 31.8000);
const northEast = L.latLng(-28.8000, 31.9000);
const ALLOWED_BOUNDS = L.latLngBounds(southWest, northEast);

function isWithinAllowedArea(lat, lng) {
    return ALLOWED_BOUNDS.contains([lat, lng]);
}

// Toggle custom issue input field when "other" is selected
function handleIssueTypeChange(selectElement) {
    const customGroup = document.getElementById('custom-issue-group');
    const customInput = document.getElementById('custom-issue-text');

    if (selectElement.value === 'other') {
        customGroup.style.display = 'block';
        customInput.setAttribute('required', 'required');
    } else {
        customGroup.style.display = 'none';
        customInput.removeAttribute('required');
        customInput.value = '';
    }
}

function initMap() {
    // Exact center of KwaDlangezwa
    const kwadlangezwaCenter = [-28.8583, 31.8519];

    // Initialize Leaflet map with strict scroll and drag lockdown
    map = L.map('map', {
        zoomControl: true,
        dragging: true,
        scrollWheelZoom: true,
        touchZoom: true,
        maxBounds: ALLOWED_BOUNDS,      // Hard locks panning bounds to KwaDlangezwa
        maxBoundsViscosity: 1.0,         // Prevents pulling or dragging outside the bounds
        minZoom: 14,                    // Prevents zooming out beyond the local area
        maxZoom: 18                     // Keeps max zoom practical
    }).setView(kwadlangezwaCenter, 15);

    // High-Resolution Satellite Base Layer
    const satelliteLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP',
        maxZoom: 18
    });

    // Clear Hybrid Labels & Roads Layer
    const hybridLabels = L.tileLayer('https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}', {
        attribution: 'Labels &copy; Esri',
        maxZoom: 18
    });

    satelliteLayer.addTo(map);
    hybridLabels.addTo(map);

    // Map click validation handler
    map.on('click', function(e) {
        const lat = e.latlng.lat;
        const lng = e.latlng.lng;
        const statusDiv = document.getElementById('geo-status');

        if (!isWithinAllowedArea(lat, lng)) {
            if (statusDiv) {
                statusDiv.innerHTML = "<span style='color: red;'>Location is outside KwaDlangezwa. Please pick a point within KwaDlangezwa only.</span>";
            }
            return;
        }

        if (document.getElementById('latitude')) document.getElementById('latitude').value = lat;
        if (document.getElementById('longitude')) document.getElementById('longitude').value = lng;

        if (currentMarker) {
            map.removeLayer(currentMarker);
        }

        currentMarker = L.marker([lat, lng], { draggable: true }).addTo(map)
            .bindPopup("Selected Incident Location")
            .openPopup();

        currentMarker.on('dragend', function(event) {
            const position = event.target.getLatLng();
            if (!isWithinAllowedArea(position.lat, position.lng)) {
                alert("Pinned location must be within KwaDlangezwa!");
                return;
            }
            if (document.getElementById('latitude')) document.getElementById('latitude').value = position.lat;
            if (document.getElementById('longitude')) document.getElementById('longitude').value = position.lng;
        });

        if (statusDiv) {
            statusDiv.innerHTML = "Location successfully set!";
        }
    });
}

// Automatically initialize map and adjust sizing on window load
window.onload = function() {
    initMap();
    setTimeout(function() {
        if (map) map.invalidateSize();
    }, 250);
};

// Handle camera capture input and bridge it to main form file input
function handleCameraUpload(event) {
    const cameraInput = event.target;
    const mainFileInput = document.getElementById('waste-photo');

    if (cameraInput.files && cameraInput.files[0]) {
        // Transfer file from camera input to main form input
        const dataTransfer = new DataTransfer();
        dataTransfer.items.add(cameraInput.files[0]);
        mainFileInput.files = dataTransfer.files;

        // Trigger processing
        handlePhotoUpload({ target: mainFileInput });
    }
}

// Handle photo upload with strict rejection for out-of-bounds geotags
function handlePhotoUpload(event) {
    const fileInput = event.target;
    const file = fileInput.files[0];
    const statusDiv = document.getElementById('geo-status');
    const fileNameDiv = document.getElementById('file-chosen-name');
    
    if (!file) return;

    if (fileNameDiv) fileNameDiv.innerText = `Selected File: ${file.name}`;
    if (statusDiv) statusDiv.innerHTML = "Reading photo geotag metadata...";

    const defaultLat = -28.8583;
    const defaultLng = 31.8519;

    try {
        EXIF.getData(file, function() {
            const latData = EXIF.getTag(this, "GPSLatitude");
            const latRef = EXIF.getTag(this, "GPSLatitudeRef");
            const lngData = EXIF.getTag(this, "GPSLongitude");
            const lngRef = EXIF.getTag(this, "GPSLongitudeRef");

            if (latData && lngData) {
                const parsedLat = convertDMSToDD(latData, latRef);
                const parsedLng = convertDMSToDD(lngData, lngRef);

                // Check if photo coordinates fall outside KwaDlangezwa
                if (!isWithinAllowedArea(parsedLat, parsedLng)) {
                    // Decline upload and clear file input
                    fileInput.value = "";
                    if (fileNameDiv) fileNameDiv.innerText = "No photo selected";
                    if (document.getElementById('latitude')) document.getElementById('latitude').value = "";
                    if (document.getElementById('longitude')) document.getElementById('longitude').value = "";

                    if (currentMarker) {
                        map.removeLayer(currentMarker);
                    }
                    map.setView([defaultLat, defaultLng], 15);

                    if (statusDiv) {
                        statusDiv.innerHTML = "<span style='color: red; font-weight: bold;'>❌ Invalid Photo Location! The photo geotag is outside KwaDlangezwa. Please re-upload or capture a picture taken within KwaDlangezwa.</span>";
                    }
                    alert("Upload declined: Photo location is outside KwaDlangezwa. Please capture or upload a picture within KwaDlangezwa.");
                    return;
                }

                // If valid, set coordinates
                document.getElementById('latitude').value = parsedLat;
                document.getElementById('longitude').value = parsedLng;
                const coords = [parsedLat, parsedLng];

                map.setView(coords, 17);
                if (currentMarker) map.removeLayer(currentMarker);

                currentMarker = L.marker(coords, { draggable: true }).addTo(map)
                    .bindPopup("Photo Location Captured within KwaDlangezwa!")
                    .openPopup();

                if (statusDiv) {
                    statusDiv.innerHTML = "Location successfully pinned from photo!";
                }
            } else {
                // No GPS data found in the photo
                document.getElementById('latitude').value = defaultLat;
                document.getElementById('longitude').value = defaultLng;
                map.setView([defaultLat, defaultLng], 15);

                if (currentMarker) map.removeLayer(currentMarker);
                currentMarker = L.marker([defaultLat, defaultLng], { draggable: true }).addTo(map)
                    .bindPopup("No GPS found in photo. Defaulted to KwaDlangezwa—click map to set spot.")
                    .openPopup();

                if (statusDiv) {
                    statusDiv.innerHTML = "<span style='color: orange;'>⚠️ No GPS geotag found in photo. Defaulted to KwaDlangezwa—please adjust marker on map if needed.</span>";
                }
            }
        });
    } catch (error) {
        console.warn("EXIF processing error:", error);
        if (statusDiv) {
            statusDiv.innerHTML = "<span style='color: red;'>Could not read photo metadata. Please try another image.</span>";
        }
    }
}

// Helper utility to convert EXIF coordinate arrays to decimal degrees
function convertDMSToDD(coordinateArray, ref) {
    let degrees = coordinateArray[0].numerator / coordinateArray[0].denominator;
    let minutes = coordinateArray[1].numerator / coordinateArray[1].denominator;
    let seconds = coordinateArray[2].numerator / coordinateArray[2].denominator;
    
    let decimal = degrees + (minutes / 60) + (seconds / 3600);
    if (ref === "S" || ref === "W") {
        decimal = decimal * -1;
    }
    return decimal;
}