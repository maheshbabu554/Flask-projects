/**
 * home.js
 * -------
 * Home page: shows the weather of the default city when the page opens
 * and updates it whenever the user searches for another city.
 */
"use strict";

const homeBox = document.getElementById("home");
const currentCard = document.getElementById("current-card");
const highlightsCard = document.getElementById("highlights-card");
const forecastPanel = document.getElementById("forecast-panel");

/** "Good Morning!" / "Good Afternoon!" / "Good Evening!" */
const showGreeting = () => {
  const hour = new Date().getHours();
  const word = hour < 12 ? "Morning" : hour < 17 ? "Afternoon" : "Evening";
  document.getElementById("greeting").textContent = `Good ${word}!`;
};

/** Put the server data on the screen. */
const showWeather = (data) => {
  currentCard.innerHTML = renderCurrentCard(data.place, data.weather);
  highlightsCard.innerHTML = renderHighlights(data.weather);
  forecastPanel.innerHTML = renderForecast(data.weather);
  bindForecastClicks(forecastPanel);
  bindSaveButton(data.place);
};

/** Search by a city chosen in the dropdown. */
const searchBySelect = async (place) => {
  const data = await loadWeather(placeToParams(place));
  if (data) showWeather(data);
};

/** Search by typed text (Enter / Search button). */
const searchByText = async (text) => {
  const data = await loadWeather({ city: text });
  if (data) showWeather(data);
};

/** Runs once when the page opens. */
(async () => {
  showGreeting();
  setupSearchBox(document.querySelector(".search-box"), searchBySelect, searchByText);

  // record=0 -> the automatic first load is NOT saved in History
  const data = await loadWeather(
    { city: homeBox.dataset.defaultCity, record: "0" }, false);
  if (data) showWeather(data);
  else currentCard.innerHTML = `<p class="loading">Could not load the weather.</p>`;
})();
