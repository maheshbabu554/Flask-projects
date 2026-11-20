
document.addEventListener("DOMContentLoaded", function () {

    // =====================================
    // PASSWORD SHOW / HIDE
    // =====================================

    const passwordInput = document.getElementById("password");
    const passwordToggle = document.getElementById("hwPasswordToggle");
    const passwordIcon = document.getElementById("hwPasswordIcon");

    if (passwordInput && passwordToggle && passwordIcon) {

        passwordToggle.addEventListener("click", function () {

            const isPasswordHidden =
                passwordInput.type === "password";

            passwordInput.type = isPasswordHidden ? "text" : "password";

            passwordToggle.setAttribute(
                "aria-label",
                isPasswordHidden ? "Hide password" : "Show password"
            );

            passwordToggle.setAttribute(
                "aria-pressed",
                String(isPasswordHidden)
            );

            passwordIcon.textContent = isPasswordHidden ? "◎" : "◉";

        });

    }


    // =====================================
    // LOGIN BUTTON LOADING FEEDBACK
    // =====================================

    const loginForm = document.getElementById("hwLoginForm");
    const loginButton = document.getElementById("hwLoginButton");
    const loginButtonText = document.getElementById("hwLoginButtonText");

    if (loginForm && loginButton && loginButtonText) {

        loginForm.addEventListener("submit", function (event) {

            // Allow normal browser validation.
            if (!loginForm.checkValidity()) {
                return;
            }

            loginButton.disabled = true;
            loginButtonText.textContent = "Signing In...";

        });

    }

});
