function showHome() {
    document.getElementById('home-hero').classList.remove('hidden');
    document.getElementById('login-split-container').classList.add('hidden');
}

function showLoginPage() {
    document.getElementById('home-hero').classList.add('hidden');
    document.getElementById('login-split-container').classList.remove('hidden');
}

function openInfoModal() {
    alert("EcoWatch: Digital solutions for community empowerment and waste management tracking.");
}

// Dynamically updates the identifier input label and placeholder based on the selected role
function updateRoleFields() {
    const roleSelect = document.getElementById('role');
    const label = document.getElementById('identifier-label');
    const input = document.getElementById('identifier');

    if (roleSelect && label && input) {
        if (roleSelect.value === 'Resident') {
            label.innerText = "Enter Your Email Or Number";
            input.placeholder = "Enter Your Email Or Number";
        } else {
            label.innerText = "Enter Your Staff ID";
            input.placeholder = "Enter Your Staff ID";
        }
    }
}

// Toggles the password field between hidden (password) and visible (text)
function togglePasswordVisibility() {
    const passwordInput = document.getElementById('password');
    const toggleIcon = document.getElementById('togglePassword');
    
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

// Handles external provider button interactions
function socialLogin(provider) {
    alert("Redirecting to " + provider + " authentication...");
    // You can wire up actual OAuth endpoints here later if needed (e.g., window.location.href = `/auth/${provider.toLowerCase()}`)
}

// Run role fields check on initial window load to match default option
window.onload = function() {
    updateRoleFields();
};