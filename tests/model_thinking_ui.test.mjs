import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";
import { thinkingMetadata, thinkingOptions, thinkingSelection, hasNamedThinkingLevels } from "../web_ui/js/model_thinking.mjs";

const source = await readFile(new URL("../web_ui/js/app.js", import.meta.url), "utf8");
const html = await readFile(new URL("../web_ui/gui_html.html", import.meta.url), "utf8");
const css = await readFile(new URL("../web_ui/css/style.css", import.meta.url), "utf8");
const levels = { values: ["low", "medium", "high"], default: "medium" };

test("unknown and explicitly unsupported metadata cannot imply thinking support", () => {
  for (const model of [null, {}, { name: "qwen3:8b", description: "reasoning thinking" }, { thinking: null }, { thinking: { values: [false] } }, { thinking: { values: [] } }, { thinking: { values: [4] } }]) {
    assert.equal(thinkingMetadata(model), null);
  }
  assert.equal(thinkingMetadata({ thinking: null, runtime: { thinking: levels } }), null);
  assert.deepEqual(thinkingMetadata({ runtime: { thinking: levels } }), levels);
});

test("named levels preserve exact spelling and never invent boolean options", () => {
  const metadata = thinkingMetadata({ thinking: { values: ["Low", "HIGH"], default: "HIGH" } });
  assert.deepEqual(thinkingOptions(metadata).map((option) => option.value), ["auto", "Low", "HIGH"]);
  assert.deepEqual(thinkingOptions(metadata).slice(1).map((option) => option.label), ["Low", "HIGH"]);
  assert.equal(thinkingSelection("HIGH", metadata), "HIGH");
  assert.equal(thinkingSelection("high", metadata), "auto");
  assert.equal(thinkingSelection("on", metadata), "auto");
  assert.equal(hasNamedThinkingLevels(metadata), true);
});

test("boolean metadata retains legacy on/off choices and a real auto/default", () => {
  const metadata = thinkingMetadata({ thinking: { values: [true, false], default: true } });
  assert.deepEqual(thinkingOptions(metadata).map((option) => option.value), ["auto", "on", "off"]);
  assert.equal(thinkingSelection(true, metadata), "on");
  assert.equal(thinkingSelection(false, metadata), "off");
  assert.equal(thinkingSelection("auto", metadata), "auto");
  assert.equal(thinkingSelection(null, metadata), "auto");
  assert.equal(hasNamedThinkingLevels(metadata), false);
  assert.deepEqual(thinkingOptions(thinkingMetadata({ thinking: { values: [true] } })).map((option) => option.value), ["auto", "on"]);
});

function element() {
  return { dataset: {}, attributes: {}, classList: { toggle() {} }, setAttribute(name, value) { this.attributes[name] = value; } };
}

function harness({ installed = [{ name: "custom:latest", thinking: levels }], catalog = [], selected = "custom:latest", showRouter = false } = {}) {
  const els = Object.fromEntries([
    "quickThinkingControl", "quickThinkingButton", "quickThinkingMenu", "quickThinkingMobileControl", "quickThinkingMobileButton", "quickThinkingMobileMenu", "ollamaThinkField", "ollamaThinkSelect",
    "quickModelButton", "quickModelValue", "quickModelMeta", "quickModelMenu", "quickModelMobileControl", "quickModelMobileButton", "quickModelMobileMenu",
  ].map((name) => [name, element()]));
  const state = { installedModels: installed, activeProfileId: 1, selectedLlmModel: selected, modelSettingsState: { overrides: { output_tokens: 1024, thinking_tokens: 8192 } } };
  const calls = [];
  const context = vm.createContext({
    state, els, calls, thinkingMetadata, thinkingOptions, thinkingSelection, hasNamedThinkingLevels,
    AUTO_MODEL_ID: "__auto_router__",
    MODEL_SETTINGS_OVERRIDE_KEYS: ["ollama_think", "output_tokens", "thinking_tokens"],
    getModelId: (item) => item?.id || item?.name,
    getCatalogItemById: (name) => catalog.find((item) => item.name === name),
    getActiveProfilePreferences: () => ({ settings: { show_router_thinking_toggle: showRouter } }),
    getChatModelItems: () => installed,
    describeChatModelItem: () => "",
    escapeHtml: (value) => String(value).replaceAll("&", "&amp;").replaceAll('"', "&quot;").replaceAll("<", "&lt;").replaceAll(">", "&gt;"),
    closeQuickThinkingMenu() {}, closeQuickModelMenu() {}, syncAppSelect() {}, renderModelSettings() {}, setFooter() {},
    request: async (url, options) => { calls.push({ url, ...options }); return state.modelSettingsState; },
  });
  for (const name of ["getModelThinkingMetadata", "modelSupportsThinking", "shouldShowThinkingToggleForModel", "renderQuickThinkingControl", "renderQuickModelPicker", "buildModelSettingsPayload", "saveQuickThinkingModeFlow"]) {
    const start = source.indexOf(`function ${name}(`);
    assert.notEqual(start, -1, name);
    const end = source.indexOf("\n}", start) + 2;
    vm.runInContext(`${name.startsWith("save") ? "async " : ""}${source.slice(start, end)}`, context);
  }
  return { context, els, state, calls };
}

test("installed metadata wins over catalog; custom installed models need no name heuristic", () => {
  const { context } = harness({
    installed: [{ name: "qwen3:8b", thinking: null }, { name: "custom:latest", runtime: { thinking: levels } }, { name: "disabled", thinking: { values: [false] } }],
    catalog: [{ name: "qwen3:8b", thinking: { values: [true, false] } }],
  });
  assert.equal(context.modelSupportsThinking("qwen3:8b"), false);
  assert.equal(context.modelSupportsThinking("custom:latest"), true);
  assert.equal(context.modelSupportsThinking("disabled"), false);
  assert.equal(context.modelSupportsThinking("gpt-oss:20b"), false);
});

test("Settings and desktop/mobile menus render the same exact named selection", () => {
  const { context, els } = harness();
  context.renderQuickThinkingControl("high");
  assert.equal(els.quickThinkingControl.dataset.thinkingMode, "high");
  assert.equal(els.quickThinkingMobileControl.dataset.thinkingMode, "high");
  assert.equal(els.ollamaThinkSelect.value, "high");
  assert.equal(els.ollamaThinkField.hidden, false);
  assert.equal(els.quickThinkingMenu.innerHTML, els.quickThinkingMobileMenu.innerHTML);
  assert.match(els.quickThinkingMenu.innerHTML, /data-thinking-mode="high"[^>]*aria-checked="true"/);
  assert.match(els.ollamaThinkSelect.innerHTML, /<option value="medium">medium<\/option>/);
  assert.doesNotMatch(els.quickThinkingMenu.innerHTML, /data-thinking-mode="(?:on|off)"/);
  context.renderQuickThinkingControl("auto");
  assert.equal(els.ollamaThinkSelect.value, "auto");
  assert.match(els.quickThinkingButton.attributes["aria-label"], /по умолчанию Ollama/);
});

test("unsupported models hide controls; Auto visibility remains profile-controlled", () => {
  for (const model of [{ name: "qwen3:custom" }, { name: "qwen3:custom", thinking: { values: [false] } }]) {
    const { context, els } = harness({ installed: [model], selected: model.name });
    context.renderQuickThinkingControl("on");
    assert.equal(els.quickThinkingControl.hidden, true);
    assert.equal(els.quickThinkingMobileControl.hidden, true);
    assert.equal(els.ollamaThinkField.hidden, true);
  }
  for (const showRouter of [false, true]) {
    const { context, els } = harness({ selected: "__auto_router__", showRouter });
    context.renderQuickThinkingControl("off");
    assert.equal(els.quickThinkingControl.hidden, !showRouter);
    assert.equal(els.quickThinkingMobileControl.hidden, !showRouter);
    assert.equal(els.ollamaThinkSelect.value, "off");
  }
});

test("quick picker offers named level menus and retains Qwen-style boolean switches", () => {
  const { context, els } = harness({ installed: [{ name: "custom:latest", thinking: levels }, { name: "qwen3:8b", thinking: { values: [true, false] } }, { name: "unknown" }] });
  context.renderQuickThinkingControl("medium");
  context.renderQuickModelPicker();
  assert.match(els.quickModelMenu.innerHTML, /data-quick-thinking-open="custom:latest"/);
  assert.match(els.quickModelMenu.innerHTML, /data-quick-thinking-toggle data-quick-thinking-model="qwen3:8b"/);
  assert.doesNotMatch(els.quickModelMenu.innerHTML, /data-quick-thinking-(?:open|model)="unknown"/);
  assert.equal(els.quickModelMenu.innerHTML, els.quickModelMobileMenu.innerHTML);
});

test("quick save round-trips named/auto values without resetting either token budget", async () => {
  const { context, els, calls } = harness();
  for (const value of ["high", "medium", "auto"]) {
    els.quickThinkingControl.dataset.thinkingMode = value;
    await context.saveQuickThinkingModeFlow();
    const { body } = calls.at(-1);
    assert.equal(body.ollama_think, value);
    assert.equal(body.output_tokens, 1024);
    assert.equal(body.thinking_tokens, 8192);
  }
});

test("settings select uses AppSelect, labels mode separately from trace, and saves metadata values", () => {
  assert.match(html, /id="ollamaThinkSelect" class="field__control"/);
  assert.match(html, /Режим рассуждения модели, не видимость trace/);
  assert.match(css, /#ollamaThinkField\[hidden\]\s*\{\s*display: none/);
  assert.match(source, /thinkingSelection\(els\.ollamaThinkSelect\?\.value, getModelThinkingMetadata\(modelName\)\)/);
  assert.doesNotMatch(source, /THINKING_MODEL_PATTERNS/);
});
