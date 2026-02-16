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

export function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
