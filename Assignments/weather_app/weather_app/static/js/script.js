
/* ================= WeatherApp JavaScript ================= */

// 1. Show toast messages
function showToast(message, type = "error") {
    var wrap = document.querySelector(".toast-wrap");

    if (!wrap) {
        wrap = document.createElement("div");
        wrap.className = "toast-wrap";
        document.body.appendChild(wrap);
    }

    var box = document.createElement("div");
    box.className = "flash " + type;
    box.textContent = message;
    wrap.appendChild(box);

    setTimeout(function () {
        box.remove();
    }, 4000);
}

// 2. Hide existing toast messages
document.querySelectorAll(".toast-wrap .flash").forEach(function (box) {
    setTimeout(function () {
        box.remove();
    }, 4000);
});

// 3. Show / hide password
document.querySelectorAll(".toggle-pass").forEach(function (button) {
    button.addEventListener("click", function () {
        var input = button.parentElement.querySelector("input");

        if (!input) return;

        input.type = input.type === "password" ? "text" : "password";
    });
});

// 4. Check registration passwords
var form = document.getElementById("registerForm");

if (form) {
    form.addEventListener("submit", function (event) {
        if (form.password.value !== form.confirm_password.value) {
            event.preventDefault();
            showToast("Passwords do not match.");
        }
    });
}

// 5. Google login button (demo only)
var googleButton = document.querySelector(".btn-google");

if (googleButton) {
    googleButton.addEventListener("click", function () {
        showToast("Google login is not available yet.");
    });
}

// 6. User dropdown
var userBtn = document.getElementById("userBtn");
var userMenu = document.getElementById("userMenu");

if (userBtn && userMenu) {
    userBtn.addEventListener("click", function (event) {
        event.stopPropagation();
        userMenu.classList.toggle("open");
    });
}

// 7. City three-dot menus
document.querySelectorAll(".menu-btn").forEach(function (button) {
    button.addEventListener("click", function (event) {
        event.stopPropagation();

        document.querySelectorAll(".menu-list.open").forEach(function (menu) {
            menu.classList.remove("open");
        });

        var menu = button.nextElementSibling;

        if (menu) {
            menu.classList.toggle("open");
        }
    });
});

// 8. Close menus when clicking outside
document.addEventListener("click", function () {
    document.querySelectorAll(
        ".menu-list.open, .user-menu.open"
    ).forEach(function (menu) {
        menu.classList.remove("open");
    });
});

// 9. Load city weather using async / await
async function loadWeather(card) {
    var temp = card.querySelector(".city-temp");

    try {
        var city = encodeURIComponent(card.dataset.city);
        var response = await fetch("/api/weather?city=" + city);

        if (!response.ok) {
            throw new Error("Weather request failed");
        }

        var data = await response.json();

        if (!data.ok || !data.weather) {
            temp.textContent = "N/A";
            return;
        }

        var weather = data.weather;

        temp.textContent = weather.temp + "°C";

        var icon = card.querySelector(".city-icon");

        if (icon && weather.icon) {
            icon.className = "city-icon bi " + weather.icon;
            icon.hidden = false;
        }

        var subtitle = card.querySelector(".city-sub");

        if (subtitle) {
            subtitle.textContent =
                (weather.state ? weather.state + ", " : "") +
                (weather.country || "");
        }

    } catch (error) {
        temp.textContent = "N/A";
        console.log("Weather error:", error);
    }
}

// Load weather for all saved cities
document.querySelectorAll(".city-card").forEach(function (card) {
    loadWeather(card);
});
