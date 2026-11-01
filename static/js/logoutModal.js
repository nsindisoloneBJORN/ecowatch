document.addEventListener('DOMContentLoaded', () => {
    // 1. Create and inject the modal HTML dynamically if it doesn't exist
    if (!document.getElementById('logoutModal')) {
        const modalHtml = `
            <div id="logoutModal" class="modal-overlay" style="display: none;">
                <div class="modal-content" style="max-width: 400px; text-align: center; padding: 25px; border-radius: 10px; background: #ffffff; box-shadow: 0 4px 15px rgba(0,0,0,0.2); margin: auto;">
                    <h3 style="margin-top: 0; color: #2c3e50;">Confirm Log Out</h3>
                    <p style="color: #666; font-size: 14px; margin-bottom: 25px;">Are you sure you want to log out?</p>
                    <div style="display: flex; justify-content: center; gap: 15px;">
                        <button id="cancelLogoutBtn" type="button" style="background: #95a5a6; color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; font-weight: bold;">Cancel</button>
                        <button id="confirmLogoutBtn" type="button" style="background: #e74c3c; color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; font-weight: bold;">Log Out</button>
                    </div>
                </div>
            </div>
            <style>
            .modal-overlay {
                position: fixed;
                top: 0;
                left: 0;
                width: 100vw;
                height: 100vh;
                background: rgba(0, 0, 0, 0.5);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 9999;
            }
            </style>
        `;
        document.body.insertAdjacentHTML('beforeend', modalHtml);
    }

    const logoutModal = document.getElementById('logoutModal');
    const cancelLogoutBtn = document.getElementById('cancelLogoutBtn');
    const confirmLogoutBtn = document.getElementById('confirmLogoutBtn');
    const logoutLinks = document.querySelectorAll('a[href*="/logout"], .btn-logout-link, .logout-link');

    // Intercept clicks on any logout links across the page
    logoutLinks.forEach(link => {
        link.addEventListener('click', (event) => {
            event.preventDefault(); // Stop immediate navigation
            if (logoutModal) {
                logoutModal.style.display = 'flex'; // Show the modal
            }
        });
    });

    // When user clicks Confirm inside the modal, redirect them explicitly to /logout
    if (confirmLogoutBtn) {
        confirmLogoutBtn.addEventListener('click', () => {
            window.location.href = '/logout';
        });
    }

    // Hide modal on Cancel click
    if (cancelLogoutBtn) {
        cancelLogoutBtn.addEventListener('click', () => {
            if (logoutModal) {
                logoutModal.style.display = 'none';
            }
        });
    }

    // Hide modal if clicking outside the card backdrop
    if (logoutModal) {
        logoutModal.addEventListener('click', (event) => {
            if (event.target === logoutModal) {
                logoutModal.style.display = 'none';
            }
        });
    }
});