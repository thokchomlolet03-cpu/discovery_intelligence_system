(function () {
  const STORAGE_KEY = "di-docs-theme";
  const root = document.documentElement;

  function getSavedTheme() {
    try {
      const theme = localStorage.getItem(STORAGE_KEY);
      return theme === "light" || theme === "dark" ? theme : "dark";
    } catch (error) {
      return "dark";
    }
  }

  function applyTheme(theme) {
    root.dataset.theme = theme;
    const toggle = document.getElementById("theme-toggle");
    if (toggle) {
      toggle.textContent = theme === "light" ? "Dark mode" : "Light mode";
      toggle.setAttribute("aria-label", theme === "light" ? "Switch to dark mode" : "Switch to light mode");
    }
  }

  function persistTheme(theme) {
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch (error) {
      // Ignore storage failures and keep the current in-memory theme.
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    applyTheme(getSavedTheme());
    const toggle = document.getElementById("theme-toggle");
    if (!toggle) return;
    toggle.addEventListener("click", function () {
      const nextTheme = root.dataset.theme === "light" ? "dark" : "light";
      applyTheme(nextTheme);
      persistTheme(nextTheme);
    });
  });
})();
