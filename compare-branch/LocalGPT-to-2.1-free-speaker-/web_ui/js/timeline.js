export const DEFAULT_SPEAKER_LABELS = {
  hr: "HR",
  candidate: "Кандидат",
  unknown: "Собеседник",
};

function getSpeakerLabel(role, overrides) {
  const key = (role || "").toLowerCase();
  if (overrides && overrides[key]) {
    return overrides[key];
  }
  return DEFAULT_SPEAKER_LABELS[key] || key.toUpperCase();
}

function collectRoles(items = []) {
  const base = new Set(Object.keys(DEFAULT_SPEAKER_LABELS));
  for (const item of items) {
    const speaker = (item?.speaker || "").toString().trim().toLowerCase();
    if (speaker) {
      base.add(speaker);
    }
  }
  return Array.from(base);
}

export function sanitizeHTML(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function formatTime(seconds) {
  if (!Number.isFinite(seconds)) return "0:00";
  const safe = Math.max(0, Number(seconds) || 0);
  const total = Math.round(safe);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  const mm = minutes.toString().padStart(2, "0");
  const ss = secs.toString().padStart(2, "0");
  if (hours > 0) {
    return `${hours}:${mm}:${ss}`;
  }
  return `${mm}:${ss}`;
}

export function renderTimeline(container, items = [], options = {}) {
  if (!container) return;
  const { editable = false, labels = {} } = options;
  const hasItems = Array.isArray(items) && items.length > 0;

  container.classList.remove("timeline-grid--text", "timeline-grid--timed");
  container.removeAttribute("data-mode");

  if (!hasItems) {
    container.innerHTML = '<div class="timeline-empty muted">Таймлайн появится после транскрибации.</div>';
    return;
  }

  const allRoles = collectRoles(items);
  const hasTiming = items.some((item) => Number.isFinite(item?.start) || Number.isFinite(item?.end));
  container.dataset.mode = hasTiming ? "timed" : "text";
  container.classList.toggle("timeline-grid--timed", hasTiming);
  container.classList.toggle("timeline-grid--text", !hasTiming);

  const html = items
    .map((item, index) => {
      const role = (item?.speaker || "unknown").toLowerCase();
      const label = getSpeakerLabel(role, labels);
      const text = sanitizeHTML(item?.text || "");

      if (editable) {
        const optionsHtml = allRoles
          .map((value) => {
            const optionLabel = getSpeakerLabel(value, labels);
            const selected = value === role ? " selected" : "";
            return `<option value="${sanitizeHTML(value)}"${selected}>${sanitizeHTML(optionLabel)}</option>`;
          })
          .join("");
        const rows = Math.max(2, Math.min(6, Math.ceil((item?.text || "").length / 60)));
        if (hasTiming) {
          const start = formatTime(item?.start);
          const end = formatTime(item?.end ?? item?.start);
          return `
            <div class="timeline-row timeline-${role} timeline-row--editing" data-index="${index}">
              <div class="timeline-speaker">
                <select class="timeline-speaker-select" data-index="${index}">
                  ${optionsHtml}
                </select>
              </div>
              <div class="timeline-time">${start}–${end}</div>
              <div class="timeline-text">
                <textarea class="timeline-textarea" data-index="${index}" rows="${rows}">${text}</textarea>
              </div>
            </div>
          `;
        }
        return `
          <div class="timeline-row timeline-${role} timeline-row--editing timeline-row--text" data-index="${index}">
            <div class="timeline-speaker">
              <select class="timeline-speaker-select" data-index="${index}">
                ${optionsHtml}
              </select>
            </div>
            <div class="timeline-text">
              <textarea class="timeline-textarea" data-index="${index}" rows="${rows}">${text}</textarea>
            </div>
          </div>
        `;
      }

      if (hasTiming) {
        const start = formatTime(item?.start);
        const end = formatTime(item?.end ?? item?.start);
        return `
          <div class="timeline-row timeline-${role}" data-index="${index}">
            <div class="timeline-speaker">${sanitizeHTML(label)}</div>
            <div class="timeline-time">${start}–${end}</div>
            <div class="timeline-text">${text}</div>
          </div>
        `;
      }

      return `
        <div class="timeline-row timeline-${role} timeline-row--text" data-index="${index}">
          <div class="timeline-speaker">${sanitizeHTML(label)}</div>
          <div class="timeline-text">${text}</div>
        </div>
      `;
    })
    .join("");

  container.innerHTML = html;
}

export function renderRoleLegend(element, keywords, labels = {}) {
  if (!element) return;
  if (!keywords || typeof keywords !== "object") {
    const hr = getSpeakerLabel("hr", labels);
    const candidate = getSpeakerLabel("candidate", labels);
    element.textContent = `Словарь ролей: по умолчанию (${hr} / ${candidate}).`;
    return;
  }

  const parts = Object.entries(keywords)
    .filter(([role]) => typeof role === "string")
    .map(([role, words]) => {
      const label = getSpeakerLabel(role, labels);
      const list = Array.isArray(words) ? words.join(", ") : "";
      return `${label}: ${list}`.trim();
    })
    .filter(Boolean);

  if (parts.length) {
    element.textContent = `Словарь ролей • ${parts.join(" • ")}`;
    return;
  }

  const hr = getSpeakerLabel("hr", labels);
  const candidate = getSpeakerLabel("candidate", labels);
  element.textContent = `Словарь ролей: по умолчанию (${hr} / ${candidate}).`;
}
