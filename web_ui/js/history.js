import { escapeHtml, formatDateTime, formatDuration } from "./ui.js";

export function renderHistoryList(container, items, activeId = null, options = {}) {
  if (!container) return;
  const {
    language = "en",
    locale = undefined,
    emptyText = "History is empty.",
    untitledVoice = "Untitled",
    emptyPreview = "(empty)",
    baseLabel = "base",
    processedLabel = "processed",
    deleteLabel = "Delete record",
    formatLanguage = null,
  } = options;

  if (!Array.isArray(items) || !items.length) {
    container.innerHTML = `<p class="history-empty">${escapeHtml(emptyText)}</p>`;
    return;
  }

  container.innerHTML = items
    .map((item) => {
      const activeClass = item.id === activeId ? "is-active" : "";
      const voiceLabel = item.voice_name || untitledVoice;
      const languageLabel = typeof formatLanguage === "function" ? formatLanguage(item.voice_language) : item.voice_language || "—";
      const durationLabel = formatDuration(item.processed_duration_sec || item.duration_sec, language);
      const statusLabel = item.status || "—";
      const variantLabel = item.processed_output_url ? processedLabel : baseLabel;
      const deleteTitle = escapeHtml(deleteLabel);

      return `
        <article class="history-item ${activeClass}" data-id="${escapeHtml(item.id)}">
          <button class="history-open" data-action="open" data-id="${escapeHtml(item.id)}" type="button">
            <div class="history-top">
              <span>${escapeHtml(formatDateTime(item.updated_at || item.created_at, locale))}</span>
              <span class="history-status">${escapeHtml(statusLabel)}</span>
            </div>
            <p class="history-voice">${escapeHtml(voiceLabel)} • ${escapeHtml(languageLabel)}</p>
            <p class="history-preview">${escapeHtml(item.preview || emptyPreview)}</p>
            <div class="history-meta">
              <span>${escapeHtml(durationLabel)}</span>
              <span>${escapeHtml(variantLabel)}</span>
            </div>
          </button>
          <button
            class="history-delete"
            data-action="delete"
            data-id="${escapeHtml(item.id)}"
            type="button"
            aria-label="${deleteTitle}"
            title="${deleteTitle}"
          >✕</button>
        </article>
      `;
    })
    .join("");
}
