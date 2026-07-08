(function () {
  "use strict";

  const REFRESH_MS = 5 * 60 * 1000; // 5 minutes

  function setText(selector, value) {
    const el = document.querySelector(selector);
    if (el) el.textContent = value;
  }

  async function refreshConditions() {
    try {
      const res = await fetch("/api/status");
      if (!res.ok) return;
      const data = await res.json();

      if (data.kp) {
        setText(".instrument-kp .big-number", data.kp.kp.toFixed(1));
        setText(".instrument-kp .instrument-detail", data.kp.detail);
      }

      if (data.weather && data.weather.cloud_cover !== null && data.weather.cloud_cover !== undefined) {
        setText(".instrument-cloud .big-number", Math.round(data.weather.cloud_cover));
      }
    } catch (err) {
      // Silently ignore - the page still shows the last successfully loaded values.
      console.warn("Could not refresh live conditions:", err);
    }
  }

  setInterval(refreshConditions, REFRESH_MS);
})();
