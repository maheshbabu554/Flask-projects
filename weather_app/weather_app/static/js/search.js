/**
 * search.js
 * ---------
 * Search page: search a city (with dropdown) and see its weather.
 * It can also open a city directly from the URL, e.g.
 *    /search?lat=17.38&lon=78.47&name=Hyderabad     (used by My Cities / History)
 */
"use strict";

const resultBox = document.getElementById("result");

/** Draw the current card + "Next 5 Days". */
const showResult = (data) => {
  resultBox.innerHTML = `
    <div class="glass-card current-card solid">${renderCurrentCard(data.place, data.weather)}</div>
    <h3 class="section-title">Next 5 Days</h3>
    <div class="forecast-panel plain">${renderForecast(data.weather)}</div>`;
  bindForecastClicks(resultBox);
  bindSaveButton(data.place);
};

const searchBySelect = async (place) => {
  const data = await loadWeather(placeToParams(place));
  if (data) showResult(data);
};

const searchByText = async (text) => {
  const data = await loadWeather({ city: text });
  if (data) showResult(data);
};

(async () => {
  setupSearchBox(document.querySelector(".search-box"), searchBySelect, searchByText);

  // Opened from My Cities / History? Load that city automatically.
  const params = Object.fromEntries(new URLSearchParams(window.location.search));
  if (Object.keys(params).length > 0) {
    params.record = "0";                       // do not add to History again
    const data = await loadWeather(params, false);
    if (data) showResult(data);
  }
})();
