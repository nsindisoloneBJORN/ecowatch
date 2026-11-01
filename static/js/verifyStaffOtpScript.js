document.addEventListener("DOMContentLoaded", () => {
    const otpInput = document.getElementById("otp");

    // Automatically restrict input to numeric digits only
    if (otpInput) {
        otpInput.addEventListener("input", (e) => {
            e.target.value = e.target.value.replace(/[^0-9]/g, "");
        });

        // Auto-focus input field on page load
        otpInput.focus();
    }
});