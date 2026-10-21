import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const html = readFileSync(new URL("../web_ui/gui_html.html", import.meta.url), "utf8");
const javascript = readFileSync(new URL("../web_ui/js/app.js", import.meta.url), "utf8");

test("Chat/LLM settings contain a bottom installer panel with explicit scope and status", () => {
  const panelStart = html.indexOf('id="ollamaInstallerTitle"');
  assert.notEqual(panelStart, -1);
  const panel = html.slice(panelStart, html.indexOf("</section>", panelStart));
  assert.match(panel, /id="downloadModelInput"[^>]+maxlength="1024"/);
  assert.match(panel, /id="downloadModelButton"/);
  assert.match(panel, /id="ollamaInstallerStatus"[^>]+role="status"/);
  assert.match(panel, /id="ollamaInstallerDownloads"/);
  assert.match(panel, /Команду ollama run добавлять не нужно/);
  assert.match(panel, /chat-модель появится в общем списке/);
  assert.match(panel, /выберите её вручную/);
  assert.match(panel, /placeholder="ollama pull model:tag"/);
  assert.doesNotMatch(panel, /placeholder="[^"]*ollama run/);
  assert.match(panel, /Команду ollama run добавлять не нужно/);
  assert.match(panel, /установщик её проигнорирует/);
});

test("installer parses pasted text before using the existing confirmed pull lifecycle", () => {
  assert.match(javascript, /parseOllamaInstallInput\(els\.downloadModelInput\?\.value \|\| ""\)/);
  assert.match(javascript, /await startModelDownload\(parsed\.model\)/);
  assert.match(javascript, /request\("\/models\/pull", \{ method: "POST", body: \{ model: target \} \}\)/);
  assert.match(javascript, /buildSelectableChatModels/);
  assert.match(javascript, /getSelectableChatModels\(\)/);
  assert.match(javascript, /const catalogIds = new Set\(getSelectableChatModels\(\)\.map/);
  assert.match(javascript, /const installedCatalogIds = getCatalogModels\(\)/);
  assert.match(javascript, /const installedCatalogModel = getCatalogModels\(\)\.find/);
  assert.match(javascript, /setInterval\(\(\) => \{\s*loadModels\(\{ silent: true \}\)/);
  assert.match(javascript, /renderOllamaInstallerDownloads\(\)/);
  assert.match(javascript, /data-cancel-download/);
  assert.doesNotMatch(javascript, /exec\s*\(.*ollama|spawn\s*\(.*ollama/);
});
