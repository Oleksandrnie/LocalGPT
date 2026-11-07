import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { runInNewContext } from "node:vm";

const html = await readFile(new URL("../web_ui/gui_html.html", import.meta.url), "utf8");
const javascript = await readFile(new URL("../web_ui/js/app.js", import.meta.url), "utf8");
const css = await readFile(new URL("../web_ui/css/style.css", import.meta.url), "utf8");

const helperNames = [
  "chatWaitingDotsMarkup",
  "pendingChatContextMatches",
  "assistantMessageMatchesPending",
  "shouldShowPendingChatWaitingDots",
  "shouldShowAssistantWaitingDots",
];

function helperSource(name) {
  const start = javascript.indexOf(`function ${name}(`);
  assert.ok(start >= 0, `${name} should exist`);
  const end = javascript.indexOf("\nfunction ", start + 1);
  assert.ok(end > start, `${name} should have a closing brace`);
  return javascript.slice(start, end);
}

function createHarness(overrides = {}) {
  const state = {
    pendingChatMessage: {
      id: "pending-1",
      role: "user",
      profileId: "profile-1",
      sessionId: "session-1",
      acceptedSessionId: "session-1",
      knowledgeSearchMode: false,
      showWaitingDots: true,
      taskId: "task-1",
      assistantMessageId: 42,
    },
    messages: [],
    isSending: true,
    isCancellingChatTask: false,
    chatTaskId: "task-1",
    activeProfileId: "profile-1",
    currentSessionId: "session-1",
    knowledgeSearchMode: false,
    ...overrides,
  };
  const helpers = runInNewContext(`${helperNames.map(helperSource).join("\n")}\n({
    shouldShowPendingChatWaitingDots,
    shouldShowAssistantWaitingDots,
    chatWaitingDotsMarkup,
  })`, {
    state,
    isAssistantMessageActive: (message) => !["completed", "failed", "cancelled"].includes(String(message.status || "")),
    escapeHtml: (value) => String(value ?? ""),
  });
  return { state, ...helpers };
}

test("pending wait dots are scoped and an older completed answer cannot suppress them", () => {
  const h = createHarness({
    messages: [{
      id: 17,
      task_id: "older-task",
      role: "assistant",
      session_id: "session-1",
      status: "completed",
      content: "older response",
      has_reasoning: true,
    }],
  });

  assert.equal(h.shouldShowPendingChatWaitingDots(), true);
  assert.equal(h.shouldShowPendingChatWaitingDots({ profileId: "profile-2" }), false);
  assert.equal(h.shouldShowPendingChatWaitingDots({ sessionId: "session-2" }), false);
  assert.equal(h.shouldShowPendingChatWaitingDots({ knowledgeSearchMode: true }), false);
});

test("the dots move into the exact current assistant placeholder without duplication", () => {
  const h = createHarness();
  const placeholder = {
    id: 42,
    task_id: "task-1",
    role: "assistant",
    session_id: "session-1",
    status: "generating",
    content: "",
  };
  h.state.messages = [placeholder];

  assert.equal(h.shouldShowPendingChatWaitingDots(), false);
  assert.equal(h.shouldShowAssistantWaitingDots(placeholder), true);
  assert.equal(h.shouldShowAssistantWaitingDots({ ...placeholder, session_id: "session-2" }), false);
});

test("content or actual reasoning hides dots while preserving the reasoning access control", () => {
  const h = createHarness();
  const current = {
    id: 42,
    task_id: "task-1",
    role: "assistant",
    session_id: "session-1",
    status: "generating",
    content: "",
  };

  assert.equal(h.shouldShowAssistantWaitingDots({ ...current, content: "first token" }), false);
  assert.equal(h.shouldShowAssistantWaitingDots({ ...current, has_reasoning: true }), false);
  assert.equal(h.shouldShowAssistantWaitingDots({ ...current, live_reasoning: "planning" }), false);
  h.state.messages = [{ ...current, has_reasoning: true }];
  assert.equal(h.shouldShowPendingChatWaitingDots(), false);
  assert.match(javascript, /const hasReasoning = role === "assistant"[\s\S]*message\.has_reasoning \|\| String\(message\.live_reasoning/);
  assert.match(javascript, /data-reasoning-message-id=/);
});

test("completed, failed, cancelled, and stopped tasks do not keep animating", () => {
  const h = createHarness();
  const current = {
    id: 42,
    task_id: "task-1",
    role: "assistant",
    session_id: "session-1",
    status: "generating",
    content: "",
  };

  for (const status of ["completed", "failed", "cancelled"]) {
    const terminal = { ...current, status };
    assert.equal(h.shouldShowAssistantWaitingDots(terminal), false, status);
    assert.equal(h.shouldShowPendingChatWaitingDots({ messages: [terminal] }), false, status);
  }
  assert.equal(h.shouldShowAssistantWaitingDots(current, { isSending: false }), false);
  assert.equal(h.shouldShowAssistantWaitingDots(current, { isCancelling: true }), false);
});

test("recovered active blank responses use the same dots without creating a pending message", () => {
  const h = createHarness({
    pendingChatMessage: null,
    chatTaskId: "recovered-task",
    messages: [],
  });
  const recovered = {
    id: 88,
    task_id: "recovered-task",
    role: "assistant",
    session_id: "session-1",
    status: "streaming",
    content: "",
  };

  assert.equal(h.shouldShowAssistantWaitingDots(recovered), true);
  assert.equal(h.shouldShowPendingChatWaitingDots(), false);
  assert.match(javascript, /state\.isSending = true;\s+renderMessages\(\);\s+updateSendButtonState\(\);/);
});

test("waiting dots have one stable screen-reader status and respect reduced motion", () => {
  assert.match(html, /id="chatWaitingStatus" class="chat-waiting-status" role="status" aria-live="polite" aria-atomic="true"/);
  assert.match(javascript, /function updateChatWaitingStatus\(operationId, label = ""\)/);
  assert.match(javascript, /state\.chatWaitingStatusOperationId === nextId\) return/);
  assert.match(javascript, /waitingPendingForStatus\?\.knowledgeSearchMode[\s\S]*"Ищу в базе знаний"/);
  assert.match(javascript, /function chatWaitingDotsMarkup\(\)[\s\S]*class="message-waiting-dots" aria-hidden="true"[\s\S]*aria-hidden="true"/);
  assert.match(css, /\.message-waiting-dots__dot\s*\{[\s\S]*animation:/);
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)[\s\S]*\.message-waiting-dots__dot\s*\{\s*animation: none/);
});


test('failed cancellation restores waiting state for the same active request', async () => {
  const state = {chatTaskId:'task1',pendingChatMessage:{showWaitingDots:true},isSending:true};
  const start=javascript.indexOf('async function cancelCurrentChatGeneration(');
  const end=javascript.indexOf('\n}\n',start)+2;
  const cancel=runInNewContext(`(${javascript.slice(start,end)})`,{
    state,renderMessages(){},setFooter(){},chatTaskScopedUrl:()=>'/synthetic/cancel',
    request:async()=>{throw new Error('synthetic cancellation failure')},
  });
  await cancel();
  assert.equal(state.pendingChatMessage.showWaitingDots,true);
  assert.equal(state.isCancellingChatTask,false);
  assert.equal(state.isSending,true);
});
