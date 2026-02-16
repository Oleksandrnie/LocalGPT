import { escapeHtml, formatDateTime } from "./ui.js";

export function renderHistoryList(container, items, activeId = null) {
  if (!container) return;

  if (!Array.isArray(items) || !items.length) {
    container.innerHTML = '<p class="muted">История пуста.</p>';
    return;
  }

  container.innerHTML = items
    .map((item) => {
      const activeClass = item.id === activeId ? "active" : "";
      return `
        <button class="history-item ${activeClass}" data-id="${escapeHtml(item.id)}" type="button">
          <div class="history-top">
            <span>${escapeHtml(formatDateTime(item.updated_at || item.created_at))}</span>
            <span>${escapeHtml(item.model || "—")}</span>
          </div>
          <div class="history-preview">${escapeHtml(item.preview || "(пусто)")}</div>
        </button>
      `;
    })
    .join("");
}
