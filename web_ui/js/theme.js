import { elements } from "./app-state.js";
import { getSavedTheme, setSavedTheme } from "./storage.js";

const DARK_CLASS = "theme-dark";
const LIGHT_CLASS = "theme-light";

export function applyTheme(theme) {
  const target = theme === "light" ? "light" : "dark";
  document.body.classList.remove(DARK_CLASS, LIGHT_CLASS);
  document.body.classList.add(target === "light" ? LIGHT_CLASS : DARK_CLASS);
  setSavedTheme(target);
  if (elements.themeToggle) {
    elements.themeToggle.checked = target === "dark";
    elements.themeToggle.setAttribute("aria-pressed", target === "dark" ? "true" : "false");
  }
}

export function initTheme() {
  const stored = getSavedTheme("");
  const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  const initial = stored || (prefersDark ? "dark" : "light");
  applyTheme(initial);
  if (elements.themeToggle) {
    elements.themeToggle.checked = initial === "dark";
    elements.themeToggle.addEventListener("change", (event) => {
      applyTheme(event.target.checked ? "dark" : "light");
    });
  }
}
