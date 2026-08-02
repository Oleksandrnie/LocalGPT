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
