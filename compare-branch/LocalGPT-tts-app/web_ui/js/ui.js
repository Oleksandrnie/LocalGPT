export function setStatus(element, message, tone = "info") {
  if (!element) return;
  element.textContent = message || "";
  element.classList.remove("status-error", "status-success", "status-warning");
  if (tone === "error") {
    element.classList.add("status-error");
  } else if (tone === "success") {
    element.classList.add("status-success");
  } else if (tone === "warning") {
    element.classList.add("status-warning");
  }
}

export function formatDateTime(isoString, locale = undefined) {
  if (!isoString) return "";
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return isoString;
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date);
}

export function formatDuration(value, language = "en") {
  if (value === null || value === undefined || value === "") return "—";
  const seconds = Number(value);
  if (!Number.isFinite(seconds) || seconds < 0) return "—";
  const locale = language === "uk" ? "uk-UA" : language === "ru" ? "ru-RU" : "en-US";
  const number = new Intl.NumberFormat(locale, {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
  const units = language === "en" ? { short: "sec", min: "m", sec: "s" } : { short: "с", min: "м", sec: "с" };

  if (seconds < 60) {
    return `${number.format(seconds)} ${units.short}`;
  }

  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return `${mins}${units.min} ${secs}${units.sec}`;
}

export function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
