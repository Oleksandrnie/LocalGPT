import { escapeHtml, formatDateTime } from "./ui.js";

export function renderHistoryList(container, items, activeId = null, options = {}) {
  const t = options.t || ((key) => key);
  if (!container) return;

  if (!Array.isArray(items) || !items.length) {
    container.innerHTML = `<p class="muted">${escapeHtml(t("historyEmpty"))}</p>`;
    return;
  }

  container.innerHTML = items
    .map((item) => {
      const activeClass = item.id === activeId ? "active" : "";
      return `
        <div class="history-item ${activeClass}" data-id="${escapeHtml(item.id)}">
          <button class="history-open" data-action="open" data-id="${escapeHtml(item.id)}" type="button">
            <div class="history-top">
              <span>${escapeHtml(formatDateTime(item.updated_at || item.created_at))}</span>
              <span>${escapeHtml(item.model || "—")}</span>
            </div>
            <div class="history-preview">${escapeHtml(item.preview || t("emptyPreview"))}</div>
          </button>
          <button
            class="history-delete"
            data-action="delete"
            data-id="${escapeHtml(item.id)}"
            type="button"
            title="${escapeHtml(t("delete"))}"
            aria-label="${escapeHtml(t("deleteAria"))}"
          >✕</button>
        </div>
      `;
    })
    .join("");
}
