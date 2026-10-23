
/* WeatherApp: autocomplete, toast messages, menus, and saved-city weather. */

function showToast(message, type = "error") {
    let wrap = document.querySelector(".toast-wrap");

    if (!wrap) {
        wrap = document.createElement("div");
        wrap.className = "toast-wrap";
        document.body.appendChild(wrap);
    }

    const box = document.createElement("div");
    box.className = "flash " + type;
    box.textContent = message;
    wrap.appendChild(box);

    setTimeout(() => box.remove(), 4000);
}

document.querySelectorAll(".toast-wrap .flash").forEach(box => {
    setTimeout(() => box.remove(), 4500);
});

/* City autocomplete */
document.querySelectorAll(".autocomplete-form").forEach(form => {
    const input = form.querySelector('input[name="city"]');
    const list = form.querySelector(".suggestions");

    if (!input || !list) return;

    let debounceTimer = null;
    let controller = null;
    let selectedCity = null;
    let requestNumber = 0;

    function closeList() {
        list.replaceChildren();
        list.classList.remove("open");
    }

    function showEmptyMessage(message) {
        closeList();

        const item = document.createElement("div");
        item.className = "suggestion-empty";
        item.textContent = message;

        list.appendChild(item);
        list.classList.add("open");
    }

    input.addEventListener("input", () => {
        selectedCity = null;
        clearTimeout(debounceTimer);

        // Cancel any previous autocomplete request.
        if (controller) {
            controller.abort();
            controller = null;
        }

        const query = input.value.trim();
        const thisRequest = ++requestNumber;

        closeList();

        if (query.length < 2) return;

        // Wait until typing pauses.
        debounceTimer = setTimeout(async () => {
            controller = new AbortController();

            try {
                const response = await fetch(
                    "/api/suggestions?q=" +
                    encodeURIComponent(query),
                    { signal: controller.signal }
                );

                const data = await response.json();

                // Ignore results belonging to older input.
                if (thisRequest !== requestNumber) return;

                if (!response.ok || !data.ok) {
                    showEmptyMessage(
                        data.error || "Suggestions are unavailable."
                    );
                    return;
                }

                if (!data.suggestions || data.suggestions.length === 0) {
                    showEmptyMessage("No matching cities found.");
                    return;
                }

                data.suggestions.forEach(place => {
                    const item = document.createElement("button");

                    item.type = "button";
                    item.className = "suggestion-item";
                    item.setAttribute("role", "option");
                    item.textContent = place.label;

                    item.addEventListener("click", () => {
                        // Save the exact value returned by Flask.
                        selectedCity = place.value;
                        input.value = place.value;

                        closeList();

                        // Submit only after a suggestion is selected.
                        form.requestSubmit();
                    });

                    list.appendChild(item);
                });

                list.classList.add("open");

            } catch (error) {
                if (error.name !== "AbortError") {
                    console.error("Suggestion error:", error);

                    showToast(
                        "Could not load city suggestions. Check your connection.",
                        "error"
                    );
                }
            }
        }, 600);
    });

    form.addEventListener("submit", event => {
        const value = input.value.trim();

        // Prevent manual input from being submitted.
        if (!value || !selectedCity || value !== selectedCity) {
            event.preventDefault();

            showToast(
                value
                    ? "Please select a valid city from the dropdown."
                    : "Please enter a city name.",
                "error"
            );

            input.focus();
            return;
        }

        closeList();
    });

    document.addEventListener("click", event => {
        if (!form.contains(event.target)) {
            closeList();
        }
    });
});

/* City three-dot menus */
document.querySelectorAll(".menu-btn").forEach(button => {
    button.addEventListener("click", event => {
        event.stopPropagation();

        document.querySelectorAll(".menu-list.open").forEach(menu => {
            menu.classList.remove("open");
        });

        const menu = button.nextElementSibling;

        if (menu) {
            menu.classList.toggle("open");
        }
    });
});

document.addEventListener("click", () => {
    document.querySelectorAll(".menu-list.open").forEach(menu => {
        menu.classList.remove("open");
    });
});

/* Fetch weather for saved city cards */
async function loadWeather(card) {
    const temp = card.querySelector(".city-temp");

    if (!temp) return;

    try {
        const response = await fetch(
            "/api/weather?city=" +
            encodeURIComponent(card.dataset.city)
        );

        const data = await response.json();

        if (!response.ok || !data.ok || !data.weather) {
            temp.textContent = "N/A";
            return;
        }

        const weather = data.weather;

        temp.textContent = weather.temp + "°C";

        const icon = card.querySelector(".city-icon");

        if (icon && weather.icon) {
            icon.className = "city-icon bi " + weather.icon;
            icon.hidden = false;
        }

        const subtitle = card.querySelector(".city-sub");

        if (subtitle) {
            subtitle.textContent =
                (weather.state ? weather.state + ", " : "") +
                (weather.country || "");
        }

    } catch (error) {
        temp.textContent = "N/A";
        console.error("Weather error:", error);
    }
}

document.querySelectorAll(".city-card").forEach(loadWeather);
