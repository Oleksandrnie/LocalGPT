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
  assert.match(panel, /Выполняется только pull/);
  assert.match(panel, /модель можно выбрать вручную/);
});

test("installer parses pasted text before using the existing confirmed pull lifecycle", () => {
  assert.match(javascript, /parseOllamaInstallInput\(els\.downloadModelInput\?\.value \|\| ""\)/);
  assert.match(javascript, /await startModelDownload\(parsed\.model\)/);
  assert.match(javascript, /request\("\/models\/pull", \{ method: "POST", body: \{ model: target \} \}\)/);
  assert.match(javascript, /renderOllamaInstallerDownloads\(\)/);
  assert.match(javascript, /data-cancel-download/);
  assert.doesNotMatch(javascript, /exec\s*\(.*ollama|spawn\s*\(.*ollama/);
});
