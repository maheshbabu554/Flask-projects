/**
 * settings.js
 * -----------
 * Settings page: temperature unit + clearing saved data.
 */
"use strict";

/** Save the unit as soon as a radio button is clicked. */
document.querySelectorAll('input[name="unit"]').forEach((radio) =>
  radio.addEventListener("change", async () => {
    const result = await postJson("/api/settings", { unit: radio.value });
    showToast(result.data.message || "Something went wrong.", result.ok ? "success" : "error");
  }));

document.getElementById("clear-history-btn").addEventListener("click", async () => {
  if (!confirm("Delete all search history?")) return;
  const result = await apiRequest("/api/history", { method: "DELETE" });
  showToast(result.data.message || "Something went wrong.", result.ok ? "success" : "error");
});

document.getElementById("clear-cities-btn").addEventListener("click", async () => {
  if (!confirm("Remove all saved cities?")) return;
  const result = await apiRequest("/api/cities", { method: "DELETE" });
  showToast(result.data.message || "Something went wrong.", result.ok ? "success" : "error");
});
