import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const html = readFileSync(new URL("../web_ui/gui_html.html", import.meta.url), "utf8");
const javascript = readFileSync(new URL("../web_ui/js/app.js", import.meta.url), "utf8");
const css = readFileSync(new URL("../web_ui/css/style.css", import.meta.url), "utf8");

test("composer exposes a dedicated multi-image input without replacing OCR", () => {
  assert.match(html, /id="chatImageInput"[^>]+accept="image\/png,image\/jpeg,image\/webp"[^>]+multiple/);
  assert.match(html, /id="imageMenuItem"[^>]*>Изображение</);
  assert.match(html, /id="fileMenuItem"[^>]*>Фото в текст \(OCR\)</);
  assert.match(html, /id="composerAttachments"[^>]+aria-live="polite"/);
});

test("composer validates, uploads, removes, and submits server attachment ids", () => {
  assert.match(javascript, /const CHAT_IMAGE_MIME_TYPES = new Set\(\["image\/png", "image\/jpeg", "image\/jpg", "image\/webp"\]\)/);
  assert.match(javascript, /await request\("\/chat\/attachments"/);
  assert.match(javascript, /method: "DELETE"/);
  assert.match(javascript, /payload\.attachment_ids = normalizedAttachmentIds/);
  assert.match(javascript, /consumeComposerAttachments: true/);
});

test("paste and multi-image drop share the attachment ingestion flow", () => {
  assert.match(javascript, /addEventListener\("paste"/);
  assert.match(javascript, /await addChatImageFiles\(imageFiles\)/);
  assert.match(javascript, /files\.every\(\(file\) => classifyFileKind\(file\) === "image"\)/);
  assert.match(javascript, /await addChatImageFiles\(files\)/);
});

test("attachment strip has theme, focus, error, and mobile styles", () => {
  assert.match(css, /\.composer-attachment\[data-status="error"\]/);
  assert.match(css, /\.composer-attachment__remove:focus-visible/);
  assert.match(css, /body\.theme-light \.composer-attachment/);
  assert.match(css, /@media[\s\S]+\.composer-attachments \{/);
});

test("vision context export is explicit, editable, and text-only", () => {
  assert.match(html, /id="visionRagTextInput"/);
  assert.match(html, /Изображение, base64 и локальный путь не индексируются/);
  assert.match(javascript, /data-vision-rag-index/);
  assert.match(javascript, /isChatExport \? "\/rag\/chat-contexts" : "\/rag\/vision-contexts"/);
  assert.match(javascript, /text,\s*\n\s*\},/);
});

test("settings expose a dedicated Vision tab with catalog, controls, and cache actions", () => {
  assert.match(html, /data-settings-tab="vision">Vision</);
  assert.match(html, /data-settings-tab-panel="vision"/);
  assert.match(html, /id="visionNumCtxInput"[^>]+min="4096"[^>]+max="131072"/);
  assert.match(html, /id="visionOutputTokensInput"[^>]+min="0"[^>]+max="8192"/);
  [
    "visionModelLibrary",
    "chatImagesEnabledToggle",
    "visionModelSelect",
    "visionNumCtxInput",
    "visionOutputTokensInput",
    "visionFallbackSelect",
    "visionOcrAssistSelect",
    "visionOcrLanguageInput",
    "visionMaxImagesInput",
    "visionMaxFileMbInput",
    "visionMaxTotalMbInput",
    "visionMaxMegapixelsInput",
    "visionMaxSideInput",
    "visionCacheSummary",
  ].forEach((id) => assert.match(html, new RegExp(`id="${id}"`)));
  assert.match(html, /qwen2\.5vl:3b/);
  assert.match(html, /qwen2\.5vl:7b/);
  assert.match(html, /gemma3:4b/);
  assert.match(javascript, /state\.visionModels = Array\.isArray\(data\?\.vision_catalog\)/);
  assert.match(javascript, /Runtime confirmed:/);
  assert.match(javascript, /vision_num_ctx/);
  assert.match(javascript, /vision_output_tokens/);
  assert.match(javascript, /data-vision-model-action="download"/);
  assert.match(javascript, /saveActiveProfilePreferences\(\{ settings \}\)/);
  assert.match(javascript, /\/chat\/attachments\/cache\?profile_id=/);
  assert.match(javascript, /request\("\/chat\/attachments\/cleanup"/);
});
