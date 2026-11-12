import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { runInNewContext } from "node:vm";

const javascript = await readFile(new URL("../web_ui/js/app.js", import.meta.url), "utf8");
const source = javascript.slice(
  javascript.indexOf("function chatTaskWaitTimeoutMs("),
  javascript.indexOf("function isFinalChatTaskState("),
);
const startedAt = "2026-01-01T00:00:00Z";

function runtime(extra = {}) {
  let now = Date.parse(startedAt);
  const context = {
    Date: { now: () => now, parse: Date.parse },
    runtimeDiagnosticContext: () => ({}),
    logRuntimeDiagnostic: () => {},
    chatTaskScopedUrl: () => "/synthetic-task",
    window: { setTimeout: (callback) => { now += 400000; callback(); } },
    ...extra,
  };
  runInNewContext(source, context);
  return { context, advance: (ms) => { now += ms; } };
}

test("UI wait follows advertised task budget, elapsed time and cleanup grace", () => {
  const { context, advance } = runtime();
  const task = { timeout_seconds: 900, created_at: startedAt };
  assert.equal(context.chatTaskWaitTimeoutMs(task), 930000);
  advance(400000);
  assert.equal(context.chatTaskWaitTimeoutMs(task), 530000);
  advance(600000);
  assert.equal(context.chatTaskWaitTimeoutMs(task), 1000);
  for (const invalid of [undefined, null, "invalid", 0, -1]) {
    assert.equal(context.chatTaskWaitTimeoutMs({ timeout_seconds: invalid }), 300000);
  }
});

test("polling accepts a healthy task completion after five minutes", async () => {
  let calls = 0;
  const { context } = runtime({ request: async () => ({ state: ++calls === 1 ? "generating" : "completed" }) });
  const task = await context.waitForChatTask({ id: "synthetic", timeout_seconds: 900, created_at: startedAt });
  assert.equal(task.state, "completed");
  assert.equal(calls, 2);
});

test("SSE uses the same server deadline and cancels its timer on a terminal event", async () => {
  let timerMs;
  let cleared = false;
  const listeners = {};
  const { context } = runtime({
    state: {},
    window: {
      EventSource: class { addEventListener(name, listener) { listeners[name] = listener; } },
      setTimeout: (_callback, ms) => { timerMs = ms; return 1; },
      clearTimeout: () => { cleared = true; },
    },
    interruptChatTaskEventStream: () => {}, prepareChatTaskReplay: () => {},
    closeChatTaskEventSource: () => {}, clearChatTaskReplay: () => {},
    clearChatTypingStreams: () => {}, updateAssistantMessageFromTask: () => {},
    parseSsePayload: () => ({}),
  });
  const completion = context.waitForChatTaskEvents({ id: "synthetic", timeout_seconds: 900, created_at: startedAt });
  assert.equal(timerMs, 930000);
  listeners.cancelled({ data: "{}" });
  assert.equal((await completion).state, "cancelled");
  assert.equal(cleared, true);
});
