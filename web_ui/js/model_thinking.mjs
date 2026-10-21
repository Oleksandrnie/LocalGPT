// Ollama metadata is authoritative: model names/descriptions never imply support.
export function thinkingMetadata(model) {
  const raw = Object.hasOwn(model || {}, "thinking") ? model.thinking : model?.runtime?.thinking;
  if (!raw || !Array.isArray(raw.values) || !raw.values.length) return null;
  if (!raw.values.every((value) => typeof value === "boolean" || (typeof value === "string" && value.length > 0))) return null;
  const values = [...new Set(raw.values)];
  if (!values.some((value) => value !== false)) return null;
  const defaultValue = values.includes(raw.default) ? raw.default : null;
  return { values, default: defaultValue };
}

export function thinkingOptions(metadata) {
  if (!metadata) return [];
  const defaultLabel = metadata.default === true ? "Включено" : metadata.default === false ? "Выключено" : metadata.default;
  return [
    { value: "auto", label: `Auto — по умолчанию Ollama${defaultLabel ? ` (${defaultLabel})` : ""}` },
    ...metadata.values.map((value) => ({
      value: value === true ? "on" : value === false ? "off" : value,
      label: value === true ? "Включено" : value === false ? "Выключено" : value,
    })),
  ];
}

export function thinkingSelection(value, metadata) {
  // Preserve named levels verbatim, including their case, before legacy boolean normalization.
  if (typeof value === "string" && metadata?.values.includes(value)) return value;
  const normalized = value === true ? "on" : value === false ? "off" : String(value ?? "auto").trim().toLowerCase();
  return thinkingOptions(metadata).some((option) => option.value === normalized) ? normalized : "auto";
}

export function hasNamedThinkingLevels(metadata) {
  return Boolean(metadata?.values.some((value) => typeof value === "string"));
}
