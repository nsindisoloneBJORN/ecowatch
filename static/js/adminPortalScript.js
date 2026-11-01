const menuToggle = document.getElementById('menuToggle');
const adminDropdown = document.getElementById('adminDropdown');

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

// --- Admin Notification Polling & Toast Logic ---
document.addEventListener("DOMContentLoaded", function () {
    async function checkAdminNotifications() {
        try {
            const response = await fetch('/api/administrator/notifications');
            if (!response.ok) return;
            
            const data = await response.json();
            
            const badge = document.getElementById('admin-notif-badge');
            if (badge) {
                if (data.unread_count > 0) {
                    badge.innerText = data.unread_count;
                    badge.style.display = 'inline-block';
                } else {
                    badge.style.display = 'none';
                }
            }

            if (data.notifications && data.notifications.length > 0) {
                const latest = data.notifications[0];
                const lastSeenId = localStorage.getItem('last_seen_admin_notif');
                if (lastSeenId != latest.notification_id) {
                    showAdminToast(latest.title, latest.message);
                    localStorage.setItem('last_seen_admin_notif', latest.notification_id);
                }
            }
        } catch (err) {
            console.error("Error fetching admin notifications:", err);
        }
    }

    function showAdminToast(title, message) {
        let toastContainer = document.getElementById('admin-toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.id = 'admin-toast-container';
            toastContainer.style.cssText = 'position: fixed; bottom: 20px; right: 20px; z-index: 9999; display: flex; flex-direction: column; gap: 10px;';
            document.body.appendChild(toastContainer);
        }

        const toast = document.createElement('div');
        toast.style.cssText = 'background: #2b2d42; color: #fff; padding: 15px 20px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); min-width: 280px; border-left: 5px solid #4ea8de;';
        toast.innerHTML = `<strong>${title}</strong><p style="margin: 5px 0 0 0; font-size: 13px; color: #edf2f4;">${message}</p>`;
        
        toastContainer.appendChild(toast);

        setTimeout(() => {
            toast.remove();
        }, 5000);
    }

    const bellIcon = document.getElementById('admin-bell-icon');
    if (bellIcon) {
        bellIcon.addEventListener('click', async function (e) {
            e.preventDefault();
            await fetch('/api/administrator/notifications/mark-read', { method: 'POST' });
            const badge = document.getElementById('admin-notif-badge');
            if (badge) badge.style.display = 'none';
        });
    }

    checkAdminNotifications();
    setInterval(checkAdminNotifications, 30000);
});