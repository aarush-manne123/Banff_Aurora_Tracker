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

  // Forecast tab switching
  const forecastTabs = document.querySelectorAll('.forecast-tab');
  const forecastDays = document.querySelectorAll('.forecast-day');

  forecastTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const dayIndex = tab.getAttribute('data-day');

      // Remove active class from all tabs and days
      forecastTabs.forEach(t => t.classList.remove('active'));
      forecastDays.forEach(d => d.classList.remove('active'));

      // Add active class to clicked tab and corresponding day
      tab.classList.add('active');
      const targetDay = document.querySelector(`.forecast-day[data-day="${dayIndex}"]`);
      if (targetDay) {
        targetDay.classList.add('active');
      }
    });
  });
  // Contact method toggle (email / phone)
  const toggleBtns = document.querySelectorAll('.toggle-btn');
  const contactMethodInput = document.getElementById('contact_method');
  const emailFields = document.getElementById('email-fields');
  const phoneFields = document.getElementById('phone-fields');

  toggleBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const method = btn.getAttribute('data-method');

      toggleBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      if (contactMethodInput) contactMethodInput.value = method;

      if (method === 'email') {
        if (emailFields) emailFields.style.display = '';
        if (phoneFields) phoneFields.style.display = 'none';
      } else {
        if (emailFields) emailFields.style.display = 'none';
        if (phoneFields) phoneFields.style.display = '';
      }
    });
  });
})();
