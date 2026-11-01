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