import assert from "node:assert/strict";
import test from "node:test";

import { buildSelectableChatModels } from "../web_ui/js/chat_model_catalog.mjs";

test("selectable chat catalog includes installed non-catalog models without duplicating configured entries", () => {
  const models = buildSelectableChatModels(
    [{ id: "qwen2.5:7b-instruct", title: "Qwen 2.5 7B" }],
    [{ id: "qwen3:0.6b" }, { id: "qwen2.5vl:3b" }],
    [
      { id: "catalog-digest", name: "qwen2.5:7b-instruct", capabilities: ["completion"] },
      { id: "custom-digest", name: "hf.co/example/custom-model:Q4_K_M", capabilities: ["completion"] },
      { id: "router-digest", name: "qwen3:0.6b", capabilities: ["completion"] },
      { id: "vision-digest", name: "qwen2.5vl:3b", capabilities: ["completion", "vision"] },
    ],
  );

  assert.deepEqual(models.map((item) => item.id), [
    "qwen2.5:7b-instruct",
    "hf.co/example/custom-model:Q4_K_M",
  ]);
  assert.equal(models[1].custom_installed, true);
  assert.equal(models[1].title, "hf.co/example/custom-model:Q4_K_M");
  assert.notEqual(models[1].id, "custom-digest");
});

test("embedding-only installed models are not offered as chat models", () => {
  const models = buildSelectableChatModels([], [], [
    { name: "embeddinggemma:latest", capabilities: ["embedding"] },
    { name: "custom-multitask:latest", capabilities: ["completion", "embedding"] },
    { name: "unknown-capabilities:latest" },
  ]);

  assert.deepEqual(models.map((item) => item.id), [
    "custom-multitask:latest",
    "unknown-capabilities:latest",
  ]);
});
