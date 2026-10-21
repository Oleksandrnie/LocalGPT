// This is a parser, never a shell runner. Keep model syntax aligned with the backend.
const MODEL_REF = /^(?:[A-Za-z0-9][A-Za-z0-9._-]*(?::[0-9]+)?\/)*[A-Za-z0-9][A-Za-z0-9._-]*(?::[A-Za-z0-9_][A-Za-z0-9._-]*)?$/;
const INVALID_INPUT = "Укажите модель Ollama или одну команду ollama pull <модель> и необязательную ollama run с той же моделью. Другие команды и shell-синтаксис запрещены.";

export function isOllamaModelRef(value) {
  return typeof value === "string" && value.length <= 200 && MODEL_REF.test(value);
}

export function parseOllamaInstallInput(value) {
  if (typeof value !== "string" || value.length > 1024 || /[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/.test(value)) {
    throw new Error(INVALID_INPUT);
  }
  const input = value.trim();
  if (isOllamaModelRef(input)) return { model: input, ignoredRun: false };
  const lines = input.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  if (lines.length < 1 || lines.length > 2) throw new Error(INVALID_INPUT);
  const pull = /^ollama +pull +([^ ]+)$/.exec(lines[0]);
  if (!pull || !isOllamaModelRef(pull[1])) throw new Error(INVALID_INPUT);
  if (lines.length === 2 && lines[1] !== `ollama run ${pull[1]}`) throw new Error(INVALID_INPUT);
  return { model: pull[1], ignoredRun: lines.length === 2 };
}
