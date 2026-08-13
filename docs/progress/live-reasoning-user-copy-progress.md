# Live Reasoning and User Copy Progress

## Task

- Goal: stream model reasoning into the existing terminal modal during generation and add the existing copy action to user messages.
- Problem: reasoning is currently accumulated only inside the worker and becomes visible after completion; user messages expose RAG but not Copy.
- Expected result: the terminal icon appears after the first reasoning chunk, an open modal updates live, accumulated reasoning survives close/reopen and terminal states, and user Copy preserves the exact message text.
- Source specification: user message dated 2026-08-13 in this task.
- Branch: `feature/chat-thinking-reasoning-rag`; continue in place, no new branch.
- Started: 2026-08-13.
- Current status: in_progress.
- Current stage: Stage 3 — regression, docs, and cleanup.

## Instructions and precedence

- Direct user requirements: remain on the current feature branch; implement the two stated stages; preserve reasoning/content isolation and existing RAG/assistant actions.
- Task-specific requirements: icon only after first chunk, live modal append, reopen/full accumulation, persisted terminal behavior, cancel/error safety, exact user clipboard text.
- Applicable AGENTS.md rules: substantial work uses one progress file and focused validated commits; backend routes remain thin; UI needs desktop/mobile, both themes, keyboard/focus QA.
- Conflicts and resolutions: none.
- Git authorization: repository workflow requires stage checkpoint commits; no push, merge, PR, or new branch is authorized.

## Scope lock

### In scope

- Separate reasoning chunk artifact/event path from Ollama worker through chat task SSE to active message UI.
- Incremental reasoning persistence on the existing assistant message and terminal-state retention.
- Live/reopen terminal modal state for the selected message.
- User-message Copy using the existing clipboard/status mechanism.
- Focused automated tests, proportional browser smoke, and affected documentation only.

### Out of scope

- Rendering reasoning inside assistant content, changing model prompts/budgets, non-Ollama provider work, RAG behavior changes, or redesigning message actions.

### Affected areas and expected files

- Backend: `backend/apps/chat/tasks.py`, `backend/apps/chat/routes.py`.
- UI: `web_ui/js/app.js`; CSS/HTML only if real layout/accessibility changes are required.
- Tests: `tests/test_pipeline_memory.py`, `tests/chat_reasoning_ui.test.mjs`.
- Docs: affected chat/backend/UI/testing/changelog entries only if contracts change materially.

### Dependencies and compatibility

- Reuse the existing persisted `chat_messages.reasoning`, ownership endpoint, terminal icon/modal, task artifacts, SSE replay pattern, and `copyText()` feedback.
- Existing final-only `delta` contract and history/RAG isolation must remain unchanged.

### Risks and rollback concerns

- SSE reconnect must not duplicate reasoning chunks.
- Worker cancellation can occur between chunk receipt and final result; incremental persistence must retain received reasoning.
- Modal rerender/focus behavior must not reset live text or point at the wrong assistant message.

## Baseline

- Current behavior: worker appends reasoning only to a local list; only final result persists it. SSE exposes status/model/delta/terminal events, not reasoning. Modal always fetches the completed message endpoint. `canCopy` excludes user messages.
- Existing tests: reasoning separation/persistence, final endpoint ownership, delta SSE, and static terminal UI contracts.
- Validation commands: diff/compile/JS checks, focused pipeline tests, `chat_reasoning_ui.test.mjs`, then proportional regression/browser smoke.
- Pre-existing failures: previous full suite had two isolated ASR failures; plugin registry failure was order-dependent and passed alone.
- Branch and working-tree state: clean `feature/chat-thinking-reasoning-rag` at `2d9d6bd`.
- Unrelated user changes to preserve: none.

## Architecture

- Current flow: Ollama `ChatStreamEvent.reasoning` → worker-local list → final DB/result; Ollama content → delta JSONL → SSE `delta` → UI message.
- Target flow: reasoning chunk → dedicated reasoning JSONL + incremental DB reasoning → SSE `reasoning` → active message `live_reasoning`/`has_reasoning` → open terminal modal append; final DB contract remains unchanged.
- Contracts and boundaries: reasoning uses a distinct event/artifact and never reuses `delta` or `content`.
- Data and ownership: event is task/message scoped; persisted endpoint remains profile/session ownership checked.

## Implementation stages

### Stage 1 — Live reasoning event lifecycle

- Goal: expose accumulated reasoning safely during generation and preserve it through completion/cancel/error.
- Status: completed.
- Actions: add dedicated artifact reader/writer and SSE event; persist chunks; deduplicate replay; update active message/icon/modal state; cover terminal cases.
- Expected result: first chunk reveals icon; open modal grows live; close/reopen shows full current text; main content remains final-only.
- Validation: focused worker/artifact/SSE tests, static UI contracts, JS/compile/diff checks.
- Completion criterion: all Stage 1 acceptance checks pass in streaming and terminal failure paths.
- Affected files: chat tasks/routes, active UI, focused tests.
- Dependencies: existing structured Ollama stream and persisted reasoning field.
- Proposed checkpoint commit: `feat(chat): stream live reasoning to terminal modal`.

### Stage 2 — User message Copy

- Goal: add Copy to every non-empty user message without changing RAG or assistant Copy.
- Status: completed.
- Actions: generalize action eligibility, reuse `data-copy-index` and `copyText`, add exact-text static/browser coverage.
- Expected result: user actions include RAG and Copy; clipboard receives the selected raw content unchanged.
- Validation: focused Node contract plus desktop/mobile and light/dark smoke.
- Completion criterion: multiline Markdown/special characters copy exactly and existing actions remain intact.
- Affected files: active UI and focused UI tests; CSS only if action layout requires it.
- Dependencies: none beyond existing message renderer/clipboard helper.
- Proposed checkpoint commit: `feat(ui): add copy action to user messages`.

### Stage 3 — Regression, docs, and cleanup

- Goal: verify the combined lifecycle and leave a clean review-ready branch.
- Status: in_progress.
- Actions: proportional Python/Node regression, browser smoke, affected-doc update, final diff review, delete this progress file.
- Expected result: DoD evidence is recorded and no task-owned temporary artifact remains.
- Validation: safe baseline plus focused suites and manual UI matrix.
- Completion criterion: all relevant checks pass or exact pre-existing failures are separated; clean tree after cleanup commit.
- Affected files: affected permanent docs and this progress file.
- Dependencies: Stages 1–2.
- Proposed checkpoint commit: `docs: document live reasoning and user copy` plus final cleanup commit.

## Decisions

### Dedicated reasoning channel

- Context: ordinary `delta` is final-answer content and must stay replay-safe and reasoning-free.
- Decision: use a separate task artifact and SSE `reasoning` event with its own sequence.
- Reason: preserves the established security/rendering boundary and permits independent replay deduplication.
- Alternatives: poll the DB endpoint or embed reasoning in task status; both add latency or overload unrelated contracts.
- Consequences: one additional small append-only artifact exists only for the active task and is cleaned with task artifacts.

## Progress log

### 2026-08-13 — analysis and baseline

- Stage: Stage 1 started.
- Completed: branch/status verification, required docs and skill/template reading, task/SSE/UI path inspection, baseline static/Node and 3 focused Python tests.
- Changed: this progress file only.
- Validation: baseline passed.
- Issues: none.
- Next action: implement reasoning artifact + incremental persistence + SSE contract tests before UI consumption.

### 2026-08-13 — Stage 1 live reasoning lifecycle

- Stage: Stage 1 completed; Stage 2 started.
- Completed: dedicated reasoning JSONL with sequence, incremental assistant-message persistence, distinct SSE `reasoning` events before final deltas, reconnect deduplication, first-chunk icon state, live modal updates, snapshot merge, terminal status handling, and fresh focus restoration after message rerenders.
- Changed: chat tasks/routes, active UI, reasoning/pipeline/Vision lifecycle tests.
- Validation: diff/compile/JS checks; 69 focused Python tests; reasoning UI 6, attachment UI 6, markdown 2 Node tests.
- Issues: none; persisted normalization trims trailing outer whitespace between chunks while the live SSE preserves exact chunks and final accumulated reasoning remains unchanged.
- Next action: generalize `canCopy` to non-empty user messages and add exact raw-text clipboard contracts without changing RAG.

### 2026-08-13 — Stage 2 user Copy

- Stage: Stage 2 completed; Stage 3 started.
- Completed: Copy eligibility now includes non-empty user and assistant messages while retaining the existing raw `message.content` → `copyText()` path, success/error feedback, and unchanged RAG action.
- Changed: active UI and reasoning/action Node contract test.
- Validation: diff/JS checks; reasoning UI 7, attachment UI 6, markdown 2 Node tests.
- Issues: none; interactive clipboard and action-density checks remain in Stage 3 browser smoke.
- Next action: create Stage 2 checkpoint, then run proportional regression and browser QA with a multiline Markdown/special-character user message and a controlled slow reasoning stream.

### 2026-08-13 — Stage 3 regression, browser QA, and documentation

- Stage: Stage 3 completed; cleanup pending.
- Completed: cancel-retention coverage, chunk-only render optimization, active-modal snapshot race fix, full proportional regression, live Ollama/browser smoke, desktop/mobile dark/light visual inspection, and affected permanent documentation.
- Changed: active UI, focused reasoning tests, architecture/backend/UI/testing/changelog docs, and this progress file.
- Validation: full Node matrix passed; full Python suite passed 244/247 with the same two ASR baseline failures and one order-dependent plugin failure; focused reasoning/cancel tests passed; live qwen3:4b reasoning icon appeared while Stop was active and modal grew from 4 to 55 chars in 700 ms; close/reopen retained the accumulated stream; final live/persisted reasoning matched after outer-whitespace normalization; exact multiline Markdown/special-character user clipboard copy passed; user/assistant Copy and RAG actions remained present; 1280px and 390px dark/light views had no horizontal overflow or visual regression.
- Issues: browser QA initially exposed a duplicate-chunk race when the active modal merged a DB snapshot ahead of the SSE cursor; active generation now remains SSE-owned and persisted fetch is deferred until terminal state. Repeat smoke passed without internal duplication.
- Next action: run final static/focused validation, create the documentation checkpoint, then delete this completed progress file in the cleanup commit.

## Changed files

### Added

- `docs/progress/live-reasoning-user-copy-progress.md`.

### Modified

- `backend/apps/chat/tasks.py`, `backend/apps/chat/routes.py`.
- `web_ui/js/app.js`.
- `tests/test_pipeline_memory.py`, `tests/test_chat_vision_lifecycle.py`, `tests/chat_reasoning_ui.test.mjs`.
- `docs/ARCHITECTURE.md`, `docs/TESTING.md`, `docs/CHANGELOG.md`, `docs/knowledge/backend.md`, `docs/knowledge/ui.md`.

### Deleted

- None.

## Validation results

- Static checks: final `git diff --check`, Python compileall, and JS syntax checks passed after documentation.
- Unit/contract tests: final Node matrix 25/25 passed; 6 dedicated reasoning lifecycle/cancel tests passed; 134-test focused Python matrix reproduced only the same two known ASR failures.
- Integration/smoke tests: full Node matrix passed; full Python suite 244/247 with only the same known baseline failures.
- Manual/regression checks: real qwen3:4b live modal growth, close/reopen, persistence, exact user clipboard, unchanged assistant Copy/RAG, desktop/mobile and dark/light passed.
- Skipped checks and reasons: no heavy full transcript/ASR hardware pipeline or live network flows; outside affected scope.
- Remaining uncertainty: none within the approved scope.

## Regressions and deferred work

- New regressions: none.
- Pre-existing failures: two ASR baseline failures from prior task; plugin registry order-dependent full-suite failure.
- Resolved issues: active-modal DB snapshot could advance beyond the SSE cursor and duplicate later chunks; live generation now uses only the ordered SSE accumulator.
- Unresolved blockers: none.
- Deferred/technical debt: none.

## Documentation and permanent records

- Architecture/testing/setup docs: affected architecture and testing contracts updated; setup unchanged.
- Module knowledge docs: backend and UI contracts updated.
- Changelog/release notes: Unreleased updated.
- Backlog: no entry planned.
- Canonical project/task index: none beyond changelog.

## Checkpoints

### Stage 1

- Commit hash: `b6a540f`.
- Message: `feat(chat): stream live reasoning to terminal modal`.
- Files: task/SSE reasoning artifact, UI live/replay/modal state, and focused tests.
- Validation: 69 focused Python and 14 Node tests plus static checks.
- Notes: final-answer delta remains reasoning-free; failure path retains persisted reasoning.

### Stage 2

- Commit hash: `9142f1f`.
- Message: `feat(ui): add copy action to user messages`.
- Files: active message renderer and focused Node contract.
- Validation: 15 Node tests plus diff/JS checks.
- Notes: RAG and assistant Copy markup/handlers are unchanged.

## Continuation state

- Current stage: final validation and cleanup.
- Last completed action: repeat browser QA after resolving the active snapshot/SSE race, followed by affected documentation updates.
- Current repository state: Stages 1 and 2 committed; Stage 3 QA/docs diff pending checkpoint.
- Known risks: none within scope; known full-suite failures remain pre-existing and separated.
- Next exact action: run final validation, checkpoint Stage 3, delete this completed progress file, and create the cleanup commit.
- Next command or file: final static/focused validation from `docs/TESTING.md`.

## Final checklist

- [ ] Every approved stage is completed.
- [ ] Every acceptance criterion and Definition of Done item is checked.
- [ ] Required validation passed or limitations are explicitly accepted.
- [ ] Regressions were compared with baseline.
- [ ] Only affected permanent documentation and records were updated.
- [ ] Deferred work was captured without expanding scope.
- [ ] No unrelated changes or task-owned temporary artifacts remain.
- [ ] Final diff and working-tree state were inspected.
- [ ] Progress file is ready to be deleted.
