import { escapeHtml, formatDateTime, formatDuration } from "./ui.js";

function versionedUrl(url, version) {
  if (!url) return "";
  const suffix = version ? `&v=${encodeURIComponent(version)}` : "";
  return `${url}${suffix}`;
}

export function renderHistoryList(container, items, activeId = null) {
  if (!container) return;

  if (!Array.isArray(items) || !items.length) {
    container.innerHTML = '<p class="history-empty">История пока пуста.</p>';
    return;
  }

  container.innerHTML = items
    .map((item) => {
      const activeClass = item.id === activeId ? "is-active" : "";
      const audioHtml = item.base_output_url
        ? `
            <audio
              class="history-audio"
              controls
              preload="none"
              src="${escapeHtml(versionedUrl(item.base_output_url, item.updated_at || item.created_at || item.id))}"
            ></audio>
          `
        : '<p class="history-muted">WAV ещё не готов.</p>';

      return `
        <article class="history-item ${activeClass}" data-id="${escapeHtml(item.id)}">
          <button class="history-open" data-action="open" data-id="${escapeHtml(item.id)}" type="button">
            <div class="history-top">
              <span>${escapeHtml(formatDateTime(item.updated_at || item.created_at))}</span>
              <span>${escapeHtml(item.status || "—")}</span>
            </div>
            <p class="history-voice">${escapeHtml(item.voice_name || "Без имени")} • ${escapeHtml(item.voice_language || "—")}</p>
            <p class="history-preview">${escapeHtml(item.preview || "(пусто)")}</p>
            <p class="history-meta">${escapeHtml(formatDuration(item.processed_duration_sec || item.duration_sec))}</p>
          </button>
          ${audioHtml}
          <button
            class="history-delete"
            data-action="delete"
            data-id="${escapeHtml(item.id)}"
            type="button"
            aria-label="Удалить запись"
            title="Удалить запись"
          >Удалить</button>
        </article>
      `;
    })
    .join("");
}
