/**
 * cities.js
 * ---------
 * My Cities page: list saved cities, add a city (pop-up with dropdown),
 * view its weather or remove it.
 */
"use strict";

const cityList = document.getElementById("city-list");
const modal = document.getElementById("add-modal");

/** Link that opens the Search page for a saved city. */
const cityLink = (c) =>
  "/search?" + new URLSearchParams({
    lat: c.latitude, lon: c.longitude, name: c.name,
    region: c.region || "", country: c.country || "",
  }).toString();

/** Load the saved cities from the server and draw them. */
const loadCities = async () => {
  const result = await apiRequest("/api/cities");
  if (!result.ok) {
    cityList.innerHTML = `<p class="loading dark">Could not load cities.</p>`;
    return;
  }
  const { cities, unit } = result.data;

  if (cities.length === 0) {
    cityList.innerHTML = `<div class="empty-state"><p>No cities saved yet. Click "+ Add City".</p></div>`;
    return;
  }

  cityList.innerHTML = cities.map((c) => `
    <div class="city-row">
      <div class="thumb">${cityThumb(c.name)}</div>
      <div class="city-info"><strong>${escapeHtml(c.name)}</strong><small>${escapeHtml(placeSubtitle(c))}</small></div>
      <div class="city-temp">
        ${c.icon ? `<span class="mini-icon">${weatherIcon(c.icon, c.is_day)}</span>` : ""}
        <strong>${c.temperature !== undefined ? c.temperature + "&deg;" + unit : "--"}</strong>
      </div>
      <div class="kebab">
        <button class="icon-btn" data-menu aria-label="Options">&#8942;</button>
        <div class="kebab-menu">
          <a href="${cityLink(c)}">View weather</a>
          <button data-remove="${c.id}">Remove</button>
        </div>
      </div>
    </div>`).join("");
};

/** One click handler for all rows (menu open/close + remove). */
cityList.addEventListener("click", async (event) => {
  const menuButton = event.target.closest("[data-menu]");
  const removeButton = event.target.closest("[data-remove]");

  if (menuButton) {
    const menu = menuButton.nextElementSibling;
    const wasOpen = menu.classList.contains("show");
    document.querySelectorAll(".kebab-menu").forEach((m) => m.classList.remove("show"));
    if (!wasOpen) menu.classList.add("show");
    return;
  }
  if (removeButton) {
    const result = await apiRequest(`/api/cities/${removeButton.dataset.remove}`, { method: "DELETE" });
    showToast(result.data.message || "Something went wrong.", result.ok ? "success" : "error");
    loadCities();
  }
});

document.addEventListener("click", (event) => {
  if (!event.target.closest(".kebab"))
    document.querySelectorAll(".kebab-menu").forEach((m) => m.classList.remove("show"));
});

/* ---------- Add City pop-up ---------- */
const addBox = setupSearchBox(
  modal.querySelector(".search-box"),

  // a city was chosen in the dropdown -> save it
  async (place) => {
    if (await saveCity(place)) closeModal();
    loadCities();
  },

  // text typed + Enter -> find the city first, then save it
  async (text) => {
    const data = await loadWeather({ city: text, record: "0" }, false);
    if (data && (await saveCity(data.place))) closeModal();
    loadCities();
  }
);

const openModal = () => {
  modal.classList.add("show");
  addBox.input.value = "";
  addBox.input.focus();
};
const closeModal = () => {
  modal.classList.remove("show");
  addBox.hide();
};

document.getElementById("add-city-btn").addEventListener("click", openModal);
document.getElementById("close-modal").addEventListener("click", closeModal);
modal.addEventListener("click", (event) => { if (event.target === modal) closeModal(); });

loadCities();
