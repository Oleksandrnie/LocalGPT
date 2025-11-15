const speakerLabels = {
  hr: "HR",
  candidate: "Кандидат",
  unknown: "Собеседник",
};

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

export function renderTimeline(container, items = []) {
  if (!container) return;
  const hasItems = Array.isArray(items) && items.length > 0;
  if (!hasItems) {
    container.innerHTML = '<div class="timeline-empty muted">Таймлайн появится после транскрибации.</div>';
    return;
  }

  const html = items
    .map((item) => {
      const role = (item?.speaker || "unknown").toLowerCase();
      const label = speakerLabels[role] || role.toUpperCase();
      const start = formatTime(item?.start);
      const end = formatTime(item?.end ?? item?.start);
      const text = sanitizeHTML(item?.text || "");
      return `
        <div class="timeline-row timeline-${role}">
          <div class="timeline-speaker">${label}</div>
          <div class="timeline-time">${start}–${end}</div>
          <div class="timeline-text">${text}</div>
        </div>
      `;
    })
    .join("");

  container.innerHTML = html;
}

export function renderRoleLegend(element, keywords) {
  if (!element) return;
  if (!keywords || typeof keywords !== "object") {
    element.textContent = "Словарь ролей: по умолчанию (HR / Кандидат).";
    return;
  }

  const parts = Object.entries(keywords)
    .filter(([role]) => typeof role === "string")
    .map(([role, words]) => {
      const label = speakerLabels[role] || role.toUpperCase();
      const list = Array.isArray(words) ? words.join(", ") : "";
      return `${label}: ${list}`.trim();
    })
    .filter(Boolean);

  element.textContent = parts.length
    ? `Словарь ролей • ${parts.join(" • ")}`
    : "Словарь ролей: по умолчанию (HR / Кандидат).";
}
