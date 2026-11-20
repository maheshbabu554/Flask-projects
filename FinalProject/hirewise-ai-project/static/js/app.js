"use strict";

/* Shared HireWise AI browser interactions. */
document.addEventListener("DOMContentLoaded", function () {
    // Mobile navigation drawer.
    const toggle = document.getElementById("sidebarToggle");
    const sidebar = document.getElementById("appSidebar");
    if (toggle && sidebar) {
        toggle.addEventListener("click", function () {
            sidebar.classList.toggle("open");
        });
        document.addEventListener("click", function (event) {
            if (window.innerWidth < 992 && sidebar.classList.contains("open") &&
                !sidebar.contains(event.target) && !toggle.contains(event.target)) {
                sidebar.classList.remove("open");
            }
        });
    }

    // Confirm before important form actions.
    document.querySelectorAll("form[data-confirm]").forEach(function (form) {
        form.addEventListener("submit", function (event) {
            if (form.dataset.confirm && !window.confirm(form.dataset.confirm)) {
                event.preventDefault();
            }
        });
    });

    // Automatically dismiss flash messages.
    document.querySelectorAll(".alert-dismissible").forEach(function (alert) {
        window.setTimeout(function () {
            if (typeof bootstrap !== "undefined") {
                bootstrap.Alert.getOrCreateInstance(alert).close();
            }
        }, 5000);
    });

    // Show selected resume names beside file controls.
    document.querySelectorAll('input[type="file"][data-show-filename]').forEach(function (input) {
        input.addEventListener("change", function () {
            const output = document.getElementById(input.dataset.showFilename);
            if (!output) return;
            const files = Array.from(input.files || []);
            output.textContent = files.length ? files.map(file => file.name).join(", ") : "No files selected.";
        });
    });
});
