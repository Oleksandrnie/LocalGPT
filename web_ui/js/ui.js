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

export function formatDateTime(isoString) {
  if (!isoString) return "";
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return isoString;
  return date.toLocaleString();
}

export function formatDuration(value) {
  if (value === null || value === undefined || value === "") return "—";
  const seconds = Number(value);
  if (!Number.isFinite(seconds) || seconds < 0) return "—";

  if (seconds < 60) {
    return `${seconds.toFixed(1)} sec`;
  }

  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return `${mins}m ${secs}s`;
}

export function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
