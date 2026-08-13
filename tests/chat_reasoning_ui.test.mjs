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
  assert.match(javascript, /MODEL_SETTINGS_OVERRIDE_KEYS = \[[\s\S]*"output_tokens",[\s\S]*"thinking_tokens",/);
  assert.match(javascript, /buildModelSettingsPayload\(\{ ollama_think: nextMode \}\)/);
});

test("reasoning is lazy-loaded into an accessible read-only dialog", () => {
  assert.match(html, /id="reasoningBackdrop"[\s\S]*role="dialog"[\s\S]*aria-modal="true"/);
  assert.match(html, /<pre[^>]+id="reasoningContent"[^>]+tabindex="0"/);
  assert.match(javascript, /\/chat\/messages\/\$\{encodeURIComponent\(id\)\}\/reasoning\?profile_id=/);
  assert.match(javascript, /data-reasoning-message-id=/);
  assert.match(javascript, /aria-label="Открыть reasoning ответа LocalGPT"/);
  assert.match(javascript, /if \(!els\.reasoningBackdrop\?\.hidden\)/);
});

test("reasoning SSE reveals the icon and updates an open modal live", () => {
  assert.match(javascript, /source\.addEventListener\("reasoning"/);
  assert.match(javascript, /consumeChatTaskReasoning\(task, data\.text, data\.sequence\)/);
  assert.match(javascript, /reasoning_delta: chunk/);
  assert.match(javascript, /has_reasoning: Boolean\(current\.has_reasoning \|\| nextReasoning \|\| updates\.has_reasoning\)/);
  assert.match(javascript, /state\.reasoningMessageId[\s\S]*els\.reasoningContent\.textContent = nextReasoning/);
  assert.match(javascript, /mergeReasoningSnapshot\(currentMessage\?\.live_reasoning, result\.reasoning\)/);
  assert.match(javascript, /lastReasoningSequence/);
});

test("reasoning controls cover focus, themes, and mobile sizing", () => {
  assert.match(javascript, /state\.reasoningReturnFocus = trigger/);
  assert.match(javascript, /returnFocus\?\.focus\?\.\(\)/);
  assert.match(css, /\.message-reasoning-button:focus-visible/);
  assert.match(css, /body\.theme-light \.reasoning-dialog__content/);
  assert.match(css, /@media[\s\S]*\.reasoning-dialog__content/);
});

test("user and completed assistant messages share an editable Chat to RAG dialog", () => {
  assert.match(javascript, /const canExportChat = hasContent && \(role === "user" \|\| \(role === "assistant" && status === "completed"\)\)/);
  assert.match(javascript, /data-chat-rag-index=/);
  assert.match(javascript, /openChatRagDialog\(chatRagButton\.dataset\.chatRagIndex, chatRagButton\)/);
  assert.match(javascript, /isChatExport \? "\/rag\/chat-contexts" : "\/rag\/vision-contexts"/);
  assert.match(javascript, /visionRagTextInput\.value = content/);
  assert.match(javascript, /state\.visionRagReturnFocus = trigger/);
});

test("user and assistant Copy share the raw message clipboard path", () => {
  assert.match(javascript, /const canCopy = hasContent && \(role === "user" \|\| role === "assistant"\)/);
  assert.match(javascript, /data-copy-index="\$\{index\}"/);
  assert.match(javascript, /const message = Number\.isFinite\(index\) \? state\.messages\[index\] : null;[\s\S]*await copyText\(message\?\.content \|\| ""\)/);
  assert.match(javascript, /setFooter\("Сообщение скопировано\.", "success"\)/);
  assert.match(javascript, /data-chat-rag-index=/);
});
