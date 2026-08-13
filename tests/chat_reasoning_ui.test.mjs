import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const html = await readFile(new URL("../web_ui/gui_html.html", import.meta.url), "utf8");
const javascript = await readFile(new URL("../web_ui/js/app.js", import.meta.url), "utf8");
const css = await readFile(new URL("../web_ui/css/style.css", import.meta.url), "utf8");

test("LLM settings expose separate output and thinking budgets", () => {
  assert.match(html, /id="maxTokensInput"[\s\S]*id="thinkingTokensInput"/);
  assert.match(javascript, /output_tokens:\s*parseOptionalNumber\(els\.maxTokensInput/);
  assert.match(javascript, /thinking_tokens:\s*parseOptionalNumber\(els\.thinkingTokensInput/);
});

test("quick Thinking control is visible for declared thinking-capable models", () => {
  assert.match(javascript, /quickThinkingControl\.hidden = !shouldShowThinkingToggleForModel\(modelName\)/);
  assert.match(javascript, /quickThinkingMobileControl\.hidden = !shouldShowThinkingToggleForModel\(modelName\)/);
});

test("reasoning is lazy-loaded into an accessible read-only dialog", () => {
  assert.match(html, /id="reasoningBackdrop"[\s\S]*role="dialog"[\s\S]*aria-modal="true"/);
  assert.match(html, /<pre[^>]+id="reasoningContent"[^>]+tabindex="0"/);
  assert.match(javascript, /\/chat\/messages\/\$\{encodeURIComponent\(id\)\}\/reasoning\?profile_id=/);
  assert.match(javascript, /data-reasoning-message-id=/);
  assert.match(javascript, /aria-label="Открыть reasoning ответа LocalGPT"/);
  assert.match(javascript, /if \(!els\.reasoningBackdrop\?\.hidden\)/);
});

test("reasoning controls cover focus, themes, and mobile sizing", () => {
  assert.match(javascript, /state\.reasoningReturnFocus = trigger/);
  assert.match(javascript, /returnFocus\?\.focus\?\.\(\)/);
  assert.match(css, /\.message-reasoning-button:focus-visible/);
  assert.match(css, /body\.theme-light \.reasoning-dialog__content/);
  assert.match(css, /@media[\s\S]*\.reasoning-dialog__content/);
});
