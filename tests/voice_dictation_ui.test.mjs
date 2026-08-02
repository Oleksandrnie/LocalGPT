import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const javascript = readFileSync(new URL("../web_ui/js/app.js", import.meta.url), "utf8");

test("voice dictation blocks recording until the selected ASR runtime is ready", () => {
  assert.match(javascript, /async function startVoiceRecording\(\)[\s\S]*?getSelectedChatWhisperModel\(\)/);
  assert.match(javascript, /!isWhisperModelInstalled\(selectedModel\)/);
  assert.match(javascript, /нажмите «Дособрать» или «Загрузить»/);
  assert.match(javascript, /setSettingsTab\("asr", \{ render: false \}\)/);
  assert.match(javascript, /setLibraryOpen\("asr", true\)/);
});

test("voice dictation uses the active profile ASR language preset", () => {
  assert.match(javascript, /const promptPreset = normalizePromptPreset\(state\.selectedPromptPreset\)/);
  assert.match(javascript, /formData\.append\("prompt_preset", promptPreset\)/);
  assert.match(javascript, /formData\.append\("language", languageForPromptPreset\(promptPreset\)\)/);
});

test("very short recordings are not sent to Whisper", () => {
  assert.match(javascript, /const MIN_VOICE_RECORDING_MS = 700/);
  assert.match(javascript, /durationMs < MIN_VOICE_RECORDING_MS/);
  assert.match(javascript, /showPromptPlaceholderHint\("Запись слишком короткая/);
  assert.match(javascript, /function showPromptPlaceholderHint\(text, durationMs = 2500\)/);
});
