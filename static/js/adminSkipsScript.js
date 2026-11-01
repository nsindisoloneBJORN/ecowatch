// Toggle Hamburger Menu Script
const menuToggle = document.getElementById('menuToggle');
const adminDropdown = document.getElementById('adminDropdown');

menuToggle.addEventListener('click', (e) => {
    e.stopPropagation();
    adminDropdown.classList.toggle('active');
});

window.addEventListener('click', () => {
    if (adminDropdown.classList.contains('active')) {
        adminDropdown.classList.remove('active');
    }
});

adminDropdown.addEventListener('click', (e) => {
    e.stopPropagation();
});

// Initialize Map centered around KwaDlangezwa / Unizulu area
const map = L.map('adminMap').setView([-28.8575, 31.8533], 15);

// Add OpenStreetMap tiles
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
    maxZoom: 16,
    attribution: 'Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ'
}).addTo(map);

// Load Live Skip Bins from Database via JSON script tag element
const skipsDataElement = document.getElementById('skips-data');
if (skipsDataElement) {
    const skips = JSON.parse(skipsDataElement.textContent);

    skips.forEach(skip => {
        if (skip.latitude && skip.longitude) {
            L.circleMarker([skip.latitude, skip.longitude], {
                radius: 8,
                fillColor: "#27ae60",
                color: "#fff",
                weight: 2,
                opacity: 1,
                fillOpacity: 0.9
            }).addTo(map).bindPopup(`<b>${skip.skip_code}: ${skip.location_name}</b><br>Zone: ${skip.municipality_zone}`);
        }
    });
}

// Sample Geotagged Resident Reports (Red Markers)
const reports = [
    { id: '#REP-501', issue: 'Illegal Dumping Skip Overflow', lat: -28.8590, lng: 31.8525 }
];

reports.forEach(rep => {
    L.circleMarker([rep.lat, rep.lng], {
        radius: 8,
        fillColor: "#c0392b",
        color: "#fff",
        weight: 2,
        opacity: 1,
        fillOpacity: 0.9
    }).addTo(map).bindPopup(`<b>Incident: ${rep.id}</b><br>${rep.issue}<br><small>Geotagged Photo Attached</small>`);
});