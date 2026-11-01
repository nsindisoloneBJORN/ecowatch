function toggleMenu() {
    const container = document.getElementById('menuContainer');
    container.classList.toggle('active');
}

window.onclick = function(event) {
    if (!event.target.closest('.user-menu-container')) {
        const container = document.getElementById('menuContainer');
        if (container && container.classList.contains('active')) {
            container.classList.remove('active');
        }
    }
}