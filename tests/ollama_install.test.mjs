import assert from "node:assert/strict";
import test from "node:test";

import { isOllamaModelRef, parseOllamaInstallInput } from "../web_ui/js/ollama_install.mjs";

test("accepts a model identifier and a single Ollama pull command", () => {
  assert.equal(parseOllamaInstallInput("qwen2.5:7b-instruct").model, "qwen2.5:7b-instruct");
  assert.equal(parseOllamaInstallInput("ollama pull gpt-oss:20b").model, "gpt-oss:20b");
  assert.equal(parseOllamaInstallInput("ollama pull hf.co/user/model:Q4_K_M").model, "hf.co/user/model:Q4_K_M");
});

test("accepts the common pull/run snippet but only returns pull model and marks run ignored", () => {
  assert.deepEqual(parseOllamaInstallInput("ollama pull gpt-oss:20b\nollama run gpt-oss:20b"), {
    model: "gpt-oss:20b",
    ignoredRun: true,
  });
});

test("rejects shell syntax, arbitrary commands, extra lines and mismatched run", () => {
  [
    "ollama pull qwen2.5:7b && ollama run qwen2.5:7b",
    "ollama run qwen2.5:7b",
    "ollama pull qwen2.5:7b\nollama run mistral:7b",
    "ollama pull qwen2.5:7b\nollama run qwen2.5:7b\nrm -rf /tmp/example",
    "pip install something",
    "--help",
    "qwen2.5:7b; echo unsafe",
    "ollama pull $(whoami)",
  ].forEach((input) => assert.throws(() => parseOllamaInstallInput(input), input));
});

test("model identifiers are bounded and do not allow whitespace or option prefixes", () => {
  assert.equal(isOllamaModelRef("hf.co/user/model:Q4_K_M"), true);
  assert.equal(isOllamaModelRef("-v"), false);
  assert.equal(isOllamaModelRef(`${"a".repeat(201)}`), false);
  assert.throws(() => parseOllamaInstallInput(`ollama pull ${"a".repeat(201)}`));
});
