/**
 * main.js
 * -------
 * Shared helper functions used by every page.
 *
 *  1. showToast()        -> small message ("City fetched successfully")
 *  2. apiRequest()       -> talks to our Flask API using fetch + async/await
 *  3. loadWeather()      -> asks /api/weather and shows the success/error message
 *  4. setupSearchBox()   -> search bar + live dropdown of matching cities
 *  5. render...()        -> build the HTML of the weather cards
 */
"use strict";

/* ====================================================================
   1. TOAST MESSAGE
   ==================================================================== */
/**
 * Show a message at the top of the screen for about 3 seconds.
 * @param {string} message - text to show
 * @param {"success"|"error"} type - green or red message
 */
const showToast = (message, type = "success") => {
  const box = document.getElementById("toast-container");
  box.innerHTML = "";                       // remove the old message first
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.textContent = message;              // textContent is safe (no HTML)
  box.appendChild(toast);
  setTimeout(() => toast.classList.add("hide"), 2800);
  setTimeout(() => toast.remove(), 3200);
};

/** Make text safe before putting it inside HTML (prevents XSS). */
const escapeHtml = (text) =>
  String(text ?? "").replace(/[&<>"']/g, (ch) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]
  ));

/** "Telangana, India" from a place object. */
const placeSubtitle = (place) =>
  [place.region, place.country].filter(Boolean).join(", ");


/* ====================================================================
   2. API REQUEST
   ==================================================================== */
/**
 * Call our Flask API and always return {ok, status, data}.
 * It never throws, so the pages can simply check `result.ok`.
 */
const apiRequest = async (url, options = {}) => {
  try {
    const response = await fetch(url, options);
    let data = {};
    try {
      data = await response.json();
    } catch (jsonError) {
      data = {};
    }
    return { ok: response.ok, status: response.status, data };
  } catch (networkError) {
    return { ok: false, status: 0, data: { message: "Cannot reach the server." } };
  }
};

/** Send JSON (POST) to the API. */
const postJson = (url, body) =>
  apiRequest(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });


/* ====================================================================
   3. LOAD WEATHER
   ==================================================================== */
/**
 * Ask the server for the weather of a city.
 *
 * @param {object} params - {city:"Hyderabad"}  OR  {lat, lon, name, region, country}
 * @param {boolean} notify - show "City fetched successfully" on success?
 * @returns the server data, or null when something went wrong.
 *
 * On failure the server message ("City not found - incorrect city")
 * is ALWAYS shown immediately in red.
 */
const loadWeather = async (params, notify = true) => {
  const query = new URLSearchParams(params).toString();
  const result = await apiRequest(`/api/weather?${query}`);

  if (!result.ok) {
    showToast(result.data.message || "Something went wrong.", "error");
    return null;
  }
  if (notify) showToast(result.data.message, "success");
  return result.data;
};

/** Convert a place from the dropdown into /api/weather parameters. */
const placeToParams = (place) => ({
  lat: place.latitude,
  lon: place.longitude,
  name: place.name,
  region: place.region || "",
  country: place.country || "",
});

/** Save a city into "My Cities". */
const saveCity = async (place) => {
  const result = await postJson("/api/cities", place);
  showToast(result.data.message || "Something went wrong.", result.ok ? "success" : "error");
  return result.ok;
};


/* ====================================================================
   3b. CLIENT-SIDE CHECK  (saves useless requests)
   ==================================================================== */
// Same rule as the server (validators.py): starts with a letter, then
// letters, spaces and . , ' - only.  \p{L} means "any letter" (also ā, é ...)
const CITY_REGEX = /^\p{L}(?:[\p{L} .,'\-])*$/u;

// Wait this long after the LAST key press before asking the server.
// While the user keeps typing, no request is sent.
const TYPING_DELAY_MS = 600;

/** true when the text could be a real city name (checked in the browser). */
const looksLikeCity = (text) => text.length >= 2 && text.length <= 60 && CITY_REGEX.test(text);


/* ====================================================================
   4. SEARCH BOX WITH DROPDOWN
   ==================================================================== */
/**
 * Make a search box work.
 *
 * While the user types (2+ letters) we call /api/suggest and show every
 * matching city in a dropdown. Example: "anan" -> Anantapur, Anand ...
 *
 * @param {HTMLElement} box  - the element with class "search-box"
 * @param {function} onSelect - called with a place when a dropdown item is chosen
 * @param {function} onSubmit - called with the typed text on Enter / Search button
 */
const setupSearchBox = (box, onSelect, onSubmit) => {
  const input = box.querySelector(".city-input");
  const button = box.querySelector(".search-btn");
  const dropdown = box.querySelector(".suggestions");

  let timer = null;      // waits a little after typing stops (debounce)
  let requestId = 0;     // ignores old answers that arrive late
  let places = [];       // current dropdown cities
  let active = -1;       // keyboard-highlighted item
  const cache = new Map();      // text -> cities already received (no second request)
  const notFound = [];          // texts that found nothing (longer texts are skipped too)

  const hide = () => {
    dropdown.classList.remove("show");
    dropdown.innerHTML = "";
    places = [];
    active = -1;
  };

  const showPlaces = (list) => {
    places = list;
    dropdown.innerHTML = list.map((p, i) => `
      <li data-index="${i}">
        <svg viewBox="0 0 24 24"><path d="M12 22s7-6.2 7-12a7 7 0 1 0-14 0c0 5.8 7 12 7 12z"/><circle cx="12" cy="10" r="2.5"/></svg>
        <span><strong>${escapeHtml(p.name)}</strong><small>${escapeHtml(placeSubtitle(p))}</small></span>
      </li>`).join("");
    dropdown.classList.add("show");
  };

  const showMessage = (text) => {
    places = [];
    dropdown.innerHTML = `<li class="no-result">${escapeHtml(text)}</li>`;
    dropdown.classList.add("show");
  };

  const highlight = () => {
    dropdown.querySelectorAll("li[data-index]").forEach((li, i) =>
      li.classList.toggle("active", i === active));
  };

  /** Ask the server for matching cities and fill the dropdown. */
  const fetchSuggestions = async (text) => {
    const key = text.toLowerCase();

    // 1) already asked before? -> use the saved answer, NO request
    if (cache.has(key)) {
      showPlaces(cache.get(key));
      return;
    }
    // 2) a shorter text already found nothing? -> this one cannot match either
    if (notFound.some((bad) => key.startsWith(bad))) {
      showMessage("City not found - incorrect city");
      return;
    }

    // 3) otherwise ask the server (only ONE request)
    const myId = ++requestId;
    const result = await apiRequest(`/api/suggest?q=${encodeURIComponent(text)}`);
    if (myId !== requestId) return;                 // an older answer: ignore it

    if (result.ok) {
      cache.set(key, result.data.places);
      showPlaces(result.data.places);
    } else {
      // remember "not found" only for 3+ letters (2 letters match exact names only)
      if (result.status === 404 && key.length >= 3) notFound.push(key);
      showMessage(result.data.message || "City not found - incorrect city");
    }
  };

  const choose = (place) => {
    input.value = place.name;
    hide();
    onSelect(place);
  };

  const submit = () => {
    requestId++;                 // cancel any dropdown request in progress
    clearTimeout(timer);
    hide();
    const text = input.value.trim().replace(/\s+/g, " ");

    // wrong text is stopped HERE, so no request goes to the server
    if (text === "") {
      showToast("Please enter a city name.", "error");
      return;
    }
    if (!looksLikeCity(text)) {
      showToast("City not found - incorrect city", "error");
      return;
    }
    onSubmit(text);
  };

  input.addEventListener("input", () => {
    clearTimeout(timer);
    requestId++;                                   // forget any older request
    const text = input.value.trim().replace(/\s+/g, " ");

    if (text.length < 2) {                         // too short: no dropdown
      hide();
      return;
    }
    if (!looksLikeCity(text)) {                    // digits / symbols: no request
      showMessage("City not found - incorrect city");
      return;
    }
    // wait until the user stops typing, then send ONE request
    timer = setTimeout(() => fetchSuggestions(text), TYPING_DELAY_MS);
  });

  input.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown" && places.length) {
      event.preventDefault();
      active = (active + 1) % places.length;
      highlight();
    } else if (event.key === "ArrowUp" && places.length) {
      event.preventDefault();
      active = (active - 1 + places.length) % places.length;
      highlight();
    } else if (event.key === "Enter") {
      event.preventDefault();
      if (active >= 0 && places[active]) choose(places[active]);
      else submit();
    } else if (event.key === "Escape") {
      hide();
    }
  });

  button.addEventListener("click", submit);

  dropdown.addEventListener("click", (event) => {
    const item = event.target.closest("li[data-index]");
    if (item) choose(places[Number(item.dataset.index)]);
  });

  document.addEventListener("click", (event) => {
    if (!box.contains(event.target)) hide();      // click outside closes it
  });

  return { input, hide };
};


/* ====================================================================
   5. WEATHER ICONS (small inline SVG pictures)
   ==================================================================== */
const RAYS = [0, 45, 90, 135, 180, 225, 270, 315].map((angle) =>
  `<line x1="32" y1="5" x2="32" y2="13" stroke="#FFB300" stroke-width="4"
         stroke-linecap="round" transform="rotate(${angle} 32 32)"/>`).join("");
const SUN = `${RAYS}<circle cx="32" cy="32" r="12" fill="#FFC83D"/>`;
const MOON = `<path d="M40 12a19 19 0 1 0 13 32A16 16 0 0 1 40 12z" fill="#FFE08A"/>`;
const cloud = (color = "#F2F7FF") =>
  `<path d="M20 52a10 10 0 0 1-1.5-19.9A14 14 0 0 1 46 34a9 9 0 0 1 1 18z" fill="${color}"/>`;

/**
 * Return the SVG picture for an icon name sent by the server.
 * @param {string} name - sunny | partly | cloudy | rain | snow | storm | fog
 * @param {boolean} isDay - false shows a moon instead of a sun
 */
const weatherIcon = (name, isDay = true) => {
  const sun = isDay ? SUN : MOON;
  const shapes = {
    sunny: sun,
    partly: `<g transform="translate(-9,-9) scale(.8)">${sun}</g>${cloud()}`,
    cloudy: cloud("#C5D3E8"),
    fog: `${cloud("#C5D3E8")}<g stroke="#9DB2CF" stroke-width="3" stroke-linecap="round">
            <line x1="16" y1="56" x2="48" y2="56"/><line x1="22" y1="61" x2="42" y2="61"/></g>`,
    rain: `${cloud("#9DB2CF")}<g stroke="#3B8CFF" stroke-width="3" stroke-linecap="round">
            <line x1="25" y1="54" x2="22" y2="61"/><line x1="33" y1="54" x2="30" y2="61"/>
            <line x1="41" y1="54" x2="38" y2="61"/></g>`,
    snow: `${cloud("#C5D3E8")}<g fill="#fff"><circle cx="24" cy="58" r="2.5"/>
            <circle cx="33" cy="60" r="2.5"/><circle cx="42" cy="58" r="2.5"/></g>`,
    storm: `${cloud("#8396B3")}<polygon points="35,44 26,56 32,56 29,64 41,50 35,50" fill="#FFC83D"/>`,
  };
  return `<svg viewBox="0 0 64 64">${shapes[name] || shapes.cloudy}</svg>`;
};

/** Small line icons used in the weather cards. */
const ICON = {
  pin: `<svg viewBox="0 0 24 24"><path d="M12 22s7-6.2 7-12a7 7 0 1 0-14 0c0 5.8 7 12 7 12z"/><circle cx="12" cy="10" r="2.5"/></svg>`,
  thermometer: `<svg viewBox="0 0 24 24"><path d="M14 14.8V5a2 2 0 0 0-4 0v9.8a4 4 0 1 0 4 0z"/></svg>`,
  drop: `<svg viewBox="0 0 24 24"><path d="M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11z"/></svg>`,
  wind: `<svg viewBox="0 0 24 24"><path d="M3 8h11a3 3 0 1 0-3-3M3 12h16a3 3 0 1 1-3 3M3 16h8"/></svg>`,
  gauge: `<svg viewBox="0 0 24 24"><circle cx="12" cy="13" r="8"/><path d="M12 13l3-4M12 5v2"/></svg>`,
  sunrise: `<svg viewBox="0 0 24 24"><path d="M3 18h18M7 18a5 5 0 0 1 10 0M12 4v5M9 6l3-3 3 3"/></svg>`,
  sunset: `<svg viewBox="0 0 24 24"><path d="M3 18h18M7 18a5 5 0 0 1 10 0M12 4v5M9 7l3 3 3-3"/></svg>`,
  uv: `<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M5 19l2-2M17 7l2-2"/></svg>`,
  eye: `<svg viewBox="0 0 24 24"><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>`,
};

/** Small coloured "photo" for a city (no image files needed). */
const cityThumb = (name) => {
  let hash = 0;
  for (const ch of name) hash = (hash * 31 + ch.charCodeAt(0)) % 360;
  return `<svg viewBox="0 0 80 56" preserveAspectRatio="xMidYMid slice">
    <rect width="80" height="56" fill="hsl(${hash},70%,68%)"/>
    <circle cx="60" cy="14" r="7" fill="#fff" opacity=".8"/>
    <polygon points="0,56 22,20 40,42 56,26 80,56" fill="hsl(${hash},45%,34%)"/>
    <polygon points="0,56 14,40 30,56" fill="hsl(${hash},50%,24%)"/></svg>`;
};


/* ====================================================================
   6. RENDER THE WEATHER CARDS
   ==================================================================== */
/** Big blue card: city, date, temperature and 4 small stats. */
const renderCurrentCard = (place, weather) => {
  const c = weather.current;
  const u = weather.unit;
  const stat = (icon, label, value) =>
    `<div class="stat">${ICON[icon]}<div><small>${label}</small><strong>${value}</strong></div></div>`;

  return `
    <div class="card-head">
      <div class="place">${ICON.pin}
        <div><h2>${escapeHtml(place.name)}</h2><p>${escapeHtml(placeSubtitle(place))}</p></div>
      </div>
      <div class="datetime"><p>${c.date_text}</p><p>${c.time_text}</p>
        <button class="btn-save" id="save-city-btn">+ Save City</button>
      </div>
    </div>
    <div class="card-main">
      <div class="big-icon">${weatherIcon(c.icon, c.is_day)}</div>
      <div>
        <div class="big-temp">${c.temperature}<span>&deg;${u}</span></div>
        <p class="desc">${c.description}</p>
      </div>
    </div>
    <div class="stats">
      ${stat("thermometer", "Feels Like", `${c.feels_like}&deg;${u}`)}
      ${stat("drop", "Humidity", `${c.humidity}%`)}
      ${stat("wind", "Wind", `${c.wind} km/h`)}
      ${stat("gauge", "Pressure", `${c.pressure} hPa`)}
    </div>`;
};

/** "Today's Highlights" card. */
const renderHighlights = (weather) => {
  const h = weather.highlights;
  const row = (cls, icon, label, value) =>
    `<div class="hl-row"><span class="badge ${cls}">${ICON[icon]}</span><span>${label}</span><strong>${value}</strong></div>`;
  return `
    <h3>Today's Highlights</h3>
    ${row("b-yellow", "sunrise", "Sunrise", h.sunrise)}
    ${row("b-red", "sunset", "Sunset", h.sunset)}
    ${row("b-gold", "uv", "UV Index", `${h.uv_index} (${h.uv_text})`)}
    ${row("b-blue", "eye", "Visibility", `${h.visibility} km`)}`;
};

/** Five small day cards. The first (today) is highlighted. */
const renderForecast = (weather) =>
  weather.forecast.map((d, i) => `
    <div class="day ${i === 0 ? "active" : ""}">
      <h4>${d.day}</h4><small>${d.date}</small>
      <div class="day-icon">${weatherIcon(d.icon)}</div>
      <p class="range">${d.max}&deg; / ${d.min}&deg;</p>
      <small>${d.description}</small>
    </div>`).join("");

/** Make a clicked forecast card look selected. */
const bindForecastClicks = (container) => {
  container.querySelectorAll(".day").forEach((card) =>
    card.addEventListener("click", () => {
      container.querySelectorAll(".day").forEach((c) => c.classList.remove("active"));
      card.classList.add("active");
    }));
};

/** Connect the "+ Save City" button of the current card. */
const bindSaveButton = (place) => {
  const button = document.getElementById("save-city-btn");
  if (button) button.addEventListener("click", () => saveCity(place));
};
