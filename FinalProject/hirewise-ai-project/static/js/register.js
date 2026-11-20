
document.addEventListener("DOMContentLoaded", function () {

    // Show and hide password fields

    const passwordToggles = document.querySelectorAll(
        ".hw-register-toggle"
    );

    passwordToggles.forEach(function (toggle) {

        toggle.addEventListener("click", function () {

            const targetId = toggle.dataset.passwordTarget;
            const input = document.getElementById(targetId);

            if (!input) {
                return;
            }

            const isHidden = input.type === "password";

            input.type = isHidden ? "text" : "password";

            toggle.textContent = isHidden ? "◎" : "◉";

            toggle.setAttribute(
                "aria-label",
                isHidden ? "Hide password" : "Show password"
            );

            toggle.setAttribute(
                "aria-pressed",
                String(isHidden)
            );

        });

    });


    // Registration button loading feedback

    const form = document.getElementById("hwRegisterForm");
    const submitButton = document.getElementById("hwRegisterSubmit");
    const buttonText = document.getElementById("hwRegisterButtonText");

    if (form && submitButton && buttonText) {

        form.addEventListener("submit", function () {

            // Let browser validation run before showing loading state.
            if (!form.checkValidity()) {
                return;
            }

            submitButton.disabled = true;
            buttonText.textContent = "Submitting Registration...";

        });

    }

});
