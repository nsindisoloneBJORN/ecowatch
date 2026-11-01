// --- Admin Analytics Script ---

const menuToggle = document.getElementById('menuToggle');
const adminDropdown = document.getElementById('adminDropdown');

if (menuToggle && adminDropdown) {
    menuToggle.addEventListener('click', (e) => {
        e.stopPropagation();
        adminDropdown.classList.toggle('show');
    });

    // Close dropdown when clicking outside
    window.addEventListener('click', () => {
        if (adminDropdown.classList.contains('show')) {
            adminDropdown.classList.remove('show');
        }
    });

    adminDropdown.addEventListener('click', (e) => {
        e.stopPropagation();
    });
}