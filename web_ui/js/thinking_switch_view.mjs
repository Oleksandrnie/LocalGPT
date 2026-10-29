function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

/**
 * Render the mutually exclusive thinking choices as a sliding segmented switch.
 * `options` is an ordered list of { value, label, title? } entries including Auto.
 * Values are escaped for markup and preserved exactly for the controller.
 */
export function renderThinkingSegments(options, selectedValue, disabled = false) {
  const segments = Array.isArray(options)
    ? options.filter((option) => option && option.value !== undefined && option.value !== null)
    : [];

  if (!segments.length) return "";

  const selectedIndex = segments.findIndex((option) => option.value === selectedValue);
  const items = segments.map((option, index) => {
    const value = escapeHtml(option.value);
    const label = escapeHtml(option.label ?? option.value);
    const selected = index === selectedIndex;
    const title = escapeHtml(option.title ?? option.label ?? option.value);
    return `<button class="thinking-segments__option" type="button" role="radio" title="${title}" data-thinking-segment="${value}" data-thinking-mode="${value}" ${disabled ? "disabled" : ""} aria-checked="${selected}" tabindex="${selected || (selectedIndex < 0 && index === 0) ? "0" : "-1"}">${label}</button>`;
  }).join("");

  return `<div class="thinking-segments" role="radiogroup" aria-label="Thinking mode" style="--thinking-segment-count:${segments.length};--thinking-selected-index:${Math.max(0, selectedIndex)};--thinking-has-selection:${selectedIndex >= 0 ? 1 : 0}">${items}</div>`;
}
