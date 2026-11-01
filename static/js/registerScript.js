// Live validation as the user types
document.addEventListener('DOMContentLoaded', function() {
    const passwordInput = document.getElementById('password');
    const confirmInput = document.getElementById('confirm_password');
    const errorText = document.getElementById('passwordError');

    function checkPasswords() {
        const password = passwordInput.value;
        const confirmPassword = confirmInput.value;

        // Only check if user has started typing in the confirm box
        if (confirmPassword.length > 0) {
            if (password !== confirmPassword) {
                errorText.style.display = 'block';
                confirmInput.style.borderColor = 'red';
            } else {
                errorText.style.display = 'none';
                confirmInput.style.borderColor = '#28a745'; // Green border when matching
            }
        } else {
            errorText.style.display = 'none';
            confirmInput.style.borderColor = '';
        }
    }

    passwordInput.addEventListener('input', checkPasswords);
    confirmInput.addEventListener('input', checkPasswords);
});

// Final safety check when submitting the form
function validatePasswordMatch() {
    const password = document.getElementById('password').value;
    const confirmPassword = document.getElementById('confirm_password').value;

    if (password !== confirmPassword) {
        alert("Passwords do not match! Please fix them before registering.");
        document.getElementById('confirm_password').focus();
        return false; // Blocks form submission
    }
    return true; // Allows submission
}

// Toggles password visibility for input fields
function togglePasswordVisibility(fieldId, iconId) {
    const passwordInput = document.getElementById(fieldId);
    const toggleIcon = document.getElementById(iconId);
    
    if (passwordInput && toggleIcon) {
        if (passwordInput.type === 'password') {
            passwordInput.type = 'text';
            toggleIcon.classList.remove('fa-eye');
            toggleIcon.classList.add('fa-eye-slash');
        } else {
            passwordInput.type = 'password';
            toggleIcon.classList.remove('fa-eye-slash');
            toggleIcon.classList.add('fa-eye');
        }
    }
}