document.addEventListener('DOMContentLoaded', () => {
    const okBtn = document.getElementById('modalOkBtn');
    if (okBtn) {
        okBtn.addEventListener('click', () => {
            // Hide the modal popup overlay
            const modal = document.getElementById('duplicateModal');
            if (modal) {
                modal.style.display = 'none';
            }
            
            // Remove the blur from the form container
            const formContainer = document.querySelector('.form-container');
            if (formContainer) {
                formContainer.classList.remove('is-blurred');
            }
            
            // Reset the form fields to a fresh state
            const form = document.querySelector('form');
            if (form) {
                form.reset();
            }
        });
    }
});