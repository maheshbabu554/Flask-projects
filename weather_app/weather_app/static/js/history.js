/**
 * history.js
 * ----------
 * History page: shows previous searches and lets the user clear them.
 */
"use strict";

const historyList = document.getElementById("history-list");

/** The server stores UTC time; show it in the user's local time. */
const localTime = (utcText) =>
  new Date(utcText.replace(" ", "T") + "Z").toLocaleString();

const loadHistory = async () => {
  const result = await apiRequest("/api/history");
  if (!result.ok) {
    historyList.innerHTML = `<p class="loading dark">Could not load history.</p>`;
    return;
  }
  const rows = result.data.history;

  if (rows.length === 0) {
    historyList.innerHTML = `<div class="empty-state"><p>No searches yet.</p></div>`;
    return;
  }

  historyList.innerHTML = rows.map((r) => {
    const link = "/search?" + new URLSearchParams({
      lat: r.latitude, lon: r.longitude, name: r.name,
      region: r.region || "", country: r.country || "",
    }).toString();
    return `
      <div class="city-row">
        <div class="thumb">${cityThumb(r.name)}</div>
        <div class="city-info"><strong>${escapeHtml(r.name)}</strong><small>${escapeHtml(placeSubtitle(r))}</small></div>
        <div class="city-temp"><small>${localTime(r.searched_at)}</small></div>
        <a class="btn-small" href="${link}">View</a>
      </div>`;
  }).join("");
};

document.getElementById("clear-history-btn").addEventListener("click", async () => {
  if (!confirm("Delete all search history?")) return;
  const result = await apiRequest("/api/history", { method: "DELETE" });
  showToast(result.data.message || "Something went wrong.", result.ok ? "success" : "error");
  loadHistory();
});

loadHistory();
