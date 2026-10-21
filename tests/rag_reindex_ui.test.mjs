import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const html = fs.readFileSync(new URL("../web_ui/gui_html.html", import.meta.url), "utf8");
const js = fs.readFileSync(new URL("../web_ui/js/app.js", import.meta.url), "utf8");
const css = fs.readFileSync(new URL("../web_ui/css/style.css", import.meta.url), "utf8");

test("RAG panel exposes explicit semantic generation state and reindex action", () => {
  for (const id of [
    "ragEmbeddingCard",
    "ragEmbeddingState",
    "ragEmbeddingDetails",
    "ragReindexProgress",
    "ragReindexButton",
  ]) {
    assert.match(html, new RegExp(`id="${id}"`));
  }
  assert.match(html, /Переиндексация запускается только вручную/);
  assert.match(css, /\.rag-generation-card\[data-state="reindex_required"\]/);
  assert.match(css, /\.rag-generation-card progress/);
});

test("RAG reindex requires confirmation and polls a profile-owned task", () => {
  assert.match(js, /title: "Переиндексировать семантический индекс\?"/);
  assert.match(js, /request\("\/rag\/reindex", \{/);
  assert.match(js, /`\/rag\/reindex\/\$\{encodeURIComponent\(taskId\)\}\?\$\{query\.toString\(\)\}`/);
  assert.match(js, /profile_id: String\(profileId\)/);
  assert.match(js, /ragReindexPolling/);
  assert.match(js, /\["queued", "running"\]/);
});

test("RAG UI distinguishes source, generation, configuration, and safe failure states", () => {
  for (const state of [
    "ready",
    "ingest_required",
    "reindex_required",
    "configuration_error",
    "failed",
  ]) {
    assert.ok(js.includes(state), `missing ${state} rendering`);
  }
  for (const code of [
    "rag_embedding_configuration_error",
    "rag_embedding_provider_unavailable",
    "rag_embedding_provider_incompatible",
    "rag_embedding_source_changed",
  ]) {
    assert.ok(js.includes(code), `missing ${code} mapping`);
  }
});
