# Chat Thinking, Reasoning, and RAG Progress

## Task

- Goal: separate model reasoning from the final chat answer, persist and expose it safely, add independent thinking/output budgets, and support explicit editable Chat → RAG export for user and completed assistant messages.
- Problem: the current Ollama adapter exposes one `num_predict` budget, discards native `message.thinking`, and cannot prevent Qwen reasoning from consuming the answer budget; Chat → RAG is limited to the Vision-derived flow.
- Expected result: Thinking ON/OFF has an effective backend-owned contract, only final content enters assistant messages/history, reasoning is separately persisted and viewable, budgets are independently stored/interpreted, and both chat roles can be explicitly exported to RAG.
- Source specification: `/Users/oleksandr/.codex/attachments/5e96c149-0f7c-43c8-b4fe-dcb42432f29e/pasted-text.txt`.
- Branch: `feature/chat-thinking-reasoning-rag`, created from clean `dev` aligned with `origin/dev` on 2026-08-13.
- Started: 2026-08-13.
- Current status: in_progress.
- Current stage: Stage 3 — reasoning and settings UI.

## Instructions and precedence

- Direct user requirements: apply `project-progress-workflow` to the attached specification.
- Task-specific requirements: use a feature branch; preserve one inference flow; keep reasoning out of message content/history/RAG; validate with focused/full tests, live Qwen, migration, and UI checks.
- Applicable AGENTS.md rules: use feature boundaries, preserve profile/session ownership, create focused validated stage commits, update only affected docs, and delete this file only after genuine completion.
- Conflicts and resolutions: repository normally requires explicit branch authorization; the specification explicitly requires this branch, so it was created. Ollama/Qwen runtime facts take precedence over assumptions in the specification.
- Git authorization: stage checkpoint commits and a final cleanup commit are required by repository instructions and the invoked workflow; no push, merge, or PR is authorized.

## Scope lock

### In scope

- Native Ollama request/response/stream parsing for `think=true/false`, Qwen-compatible OFF behavior, incomplete-output detection, and one-pass budget policy.
- Backward-compatible model settings and chat-message reasoning migration/repositories.
- Persisted streaming/non-streaming assistant lifecycle and history isolation.
- LLM Settings fields, reasoning icon/modal, shared editable Chat → RAG modal/actions, responsive/theme/accessibility styling.
- Profile-owned Chat → RAG endpoint/service and source metadata for `user|assistant`.
- Focused/full regression, controlled live Qwen smoke, affected documentation, and cleanup.

### Out of scope

- Automatic RAG ingestion, exposing reasoning in normal chat content, a second inference, model-router redesign, or unrelated provider/tool refactors.
- Provider-independent native hard reasoning limits that Ollama/model APIs do not expose.
- Push, merge, or PR creation.

### Affected areas and expected files

- Runtime/lifecycle: `backend/apps/chat/services/ollama_runtime.py`, `backend/apps/chat/service.py`, `backend/apps/chat/tasks.py`, `backend/apps/chat/routes.py`.
- Persistence/settings: `app/db.py`, `app/schemas/core.py`, `app/routes/profiles.py`, `app/config.py` if defaults require it.
- RAG: `backend/apps/rag/routes.py`, `backend/apps/rag/service.py`, schemas.
- UI: `web_ui/gui_html.html`, `web_ui/js/app.js`, `web_ui/css/style.css`.
- Tests: focused Python and Node modules under `tests/`.
- Docs: `docs/ARCHITECTURE.md`, `docs/TESTING.md`, `docs/knowledge/{backend,providers,rag,ui}.md`, `docs/CHANGELOG.md`; README/backlog only if facts require it.

### Dependencies and compatibility

- Local Ollama 0.32.5 with installed `qwen3:0.6b` and `qwen3:4b`.
- Existing SQLite installations must migrate in place; clean DB initialization must match the migrated schema.
- Legacy/non-thinking models remain valid when reasoning fields/settings are absent.
- Existing Vision → RAG behavior remains supported while the text indexing primitive is reused.

### Risks and rollback concerns

- Qwen/Ollama does not expose separate native numeric reasoning/output caps; one-pass compatibility must use a bounded combined generation cap and report that policy truthfully.
- Reasoning can be large; storage/API lengths need a safety limit without silently mixing or duplicating text.
- Streaming retries must never duplicate either final deltas or persisted reasoning.
- UI actions must remain usable across active/failed/completed states and mobile layouts.

## Baseline and verified architecture

- Git: clean `dev` aligned with `origin/dev`; feature branch created; no unrelated changes.
- Existing contract: `ChatService._runtime_kwargs()` maps `ollama_think` to native boolean and maps `max_tokens` to one `options.num_predict`; `ollama_runtime` returns only content; task streaming appends every returned text chunk to assistant content.
- Existing persistence: `chat_messages` has lifecycle fields but no reasoning; `model_settings` stores `max_tokens` and `ollama_think` but no thinking budget.
- Existing RAG reuse point: `_index_text_document()` underpins explicit Vision-derived indexing with ownership checks and safe metadata.
- Existing UI: active `gui_html.html` + `app.js`; Vision → RAG already supplies an editable title/text modal; quick Thinking rendering currently collapses `auto` to visible ON.
- Static/focused baseline passed: `git diff --check`; compileall; JS syntax; markdown renderer (2); `test_model_router`, `test_chat_vision_context`, `test_vision_rag` (60); chat attachment UI (6).
- Known baseline warning: sandboxed model-list test logs an Ollama connection warning but passes with its mocked/fallback contract.

### Live Ollama audit (2026-08-13)

- `qwen3:4b`, `think=false`, `num_predict=64`: response omitted `message.thinking`, emitted reasoning-like prose in `message.content`, and ended `done_reason=length` with no concise final answer.
- `qwen3:4b`, `think=true`, `num_predict=64`: 161 reasoning characters, empty content, `done_reason=length`, `eval_count=64`.
- Streaming `think=true`, `num_predict=256`: 182 thinking chunks followed by one content chunk (`4`), `done_reason=stop`, `eval_count=186`.
- Local Modelfile always opens a `<think>` block for a new assistant turn; therefore `think=false` disables structured extraction but does not hard-disable generation for this installed Qwen template.
- Qwen's documented turn-level `/no_think` soft switch is required as a compatibility instruction for OFF on affected hybrid Qwen models; native boolean remains authoritative for structured Ollama parsing.

## Implementation stages

### Stage 1 — Runtime contract and final-only lifecycle

- Goal: return structured reasoning/final results from native Ollama and keep reasoning out of ordinary deltas/content/history.
- Status: completed.
- Actions: add structured completion/chunk contracts; preserve final-stream SSE only; add Qwen OFF compatibility instruction without persisting it; detect reasoning-only length exhaustion as failed/incomplete; cover normal and streaming paths.
- Validation: runtime payload/parser tests, task lifecycle tests, focused chat suite, short live ON/OFF payload smoke.
- Completion criterion: ON yields separate reasoning then final content; OFF yields no reasoning trace; reasoning never enters assistant content or next history prompt; empty final on exhaustion is not completed.
- Proposed checkpoint commit: `feat(chat): separate Ollama reasoning from final output`.

### Stage 2 — Independent settings and persistence

- Goal: store validated `thinking_tokens` and `output_tokens` semantics plus per-message reasoning across clean and migrated DBs.
- Status: completed.
- Actions: add columns/defaults/schema validation; migrate legacy `max_tokens` compatibly; implement bounded one-pass effective generation policy; persist reasoning in both streaming/non-streaming lifecycle.
- Validation: settings round-trip/range tests, clean/legacy migration tests, persisted task/reload/history tests.
- Completion criterion: independent backend-owned values survive reload, legacy settings remain valid, reasoning restores separately, and effective policy is explicit in used settings.
- Dependencies: Stage 1.
- Proposed checkpoint commit: `feat(chat): persist reasoning and separate token budgets`.

### Stage 3 — Reasoning and settings UI

- Goal: expose the two budgets and a per-assistant reasoning viewer without changing normal answer rendering.
- Status: in_progress.
- Actions: add settings controls; render terminal icon only for stored reasoning; add accessible read-only modal, close/Escape/focus behavior, responsive/theme styles, and static UI tests.
- Validation: Node contract tests, JS syntax, manual desktop/mobile and dark/light inspection with keyboard/focus checks.
- Completion criterion: settings round-trip from UI and the selected completed message's reasoning opens only when present.
- Dependencies: Stage 2.
- Proposed checkpoint commit: `feat(ui): expose reasoning and separate chat budgets`.

### Stage 4 — Chat messages to RAG

- Goal: explicitly export editable user or completed assistant content through a shared profile-isolated derived-text pipeline.
- Status: pending.
- Actions: generalize/reuse text indexing; add ownership/status/role validation and metadata; adapt the existing modal/action UI; keep Vision export compatibility; add retrieval/delete/isolation tests.
- Validation: focused RAG API/service tests and Node UI tests for both roles, cancel/confirm, metadata, absence of reasoning, retrieval, and independent deletion.
- Completion criterion: both roles support manual edit → ingest → retrieval with correct role metadata and no reasoning leakage.
- Dependencies: Stage 2; Stage 3 UI patterns.
- Proposed checkpoint commit: `feat(rag): add explicit chat message export`.

### Stage 5 — Regression, live acceptance, docs, and cleanup

- Goal: satisfy the complete DoD and leave a review-ready clean branch.
- Status: pending.
- Actions: full static/unit suite, clean/existing DB migration smoke, controlled live Qwen flows, manual UI matrix, affected docs/changelog, final diff/status review, then delete this progress file.
- Validation: specification command set plus new focused tests and documented manual/live evidence.
- Completion criterion: all acceptance criteria pass or an exact external blocker remains documented; no temporary/debug/unrelated changes; clean working tree after final cleanup commit.
- Dependencies: Stages 1–4.
- Proposed checkpoint commit: `docs: document chat reasoning and RAG lifecycle`.

## Decisions

### One-pass compatibility budget

- Decision: preserve `output_tokens` as the user-facing final-answer budget and `thinking_tokens` as reasoning allowance; when native hard split is unavailable, send a safety-capped combined `num_predict` only while Thinking is ON, record the effective policy, and reject reasoning-only length exhaustion as incomplete.
- Reason: Ollama 0.32.5 exposes one `num_predict`; the live 64-token test proves it is shared across reasoning and content.
- Consequence: the adapter cannot guarantee exact per-channel token counts, but it prevents the output setting from being represented as a total shared budget and avoids false completed-empty answers.

### Qwen OFF compatibility

- Decision: send native `think=false` and a transient latest-turn `/no_think` compatibility instruction for affected hybrid Qwen models; never persist the marker in chat content.
- Reason: local template/live behavior contradicts the intended boolean-only result, while Qwen documents `/no_think` as the supported turn-level switch.

### Reasoning ownership

- Decision: reasoning belongs to the assistant message row, is returned only as explicit message metadata, and is never used by prompt/history/RAG assembly.
- Reason: this naturally preserves session/profile cascade ownership without a parallel lifecycle table.

## Progress log

### 2026-08-13 — baseline and runtime audit

- Stage: 0 completed; Stage 1 started.
- Completed: branch creation, mandatory docs/code inspection, focused baseline, local Ollama/model inventory, raw non-streaming/streaming audit, Modelfile inspection, official Ollama/Qwen contract check.
- Changed: this progress file only.
- Issues: native boolean OFF is insufficient for the installed Qwen template; separate native numeric budgets are unavailable.
- Next action: implement structured runtime result/chunk contracts and failure semantics with focused tests.

### 2026-08-13 — Stage 1 runtime separation

- Stage: 1 completed; Stage 2 started.
- Completed: structured native result/stream event parsing, final-only string compatibility APIs, transient Qwen thinking marker, final-only task deltas/content, reasoning artifact accumulation, and explicit incomplete-final failure.
- Changed: `backend/apps/chat/services/ollama_runtime.py`, `backend/apps/chat/service.py`, `backend/apps/chat/tasks.py`, `tests/test_model_router.py`, `tests/test_pipeline_memory.py`.
- Validation: diff check, compileall, JS syntax, 62 focused chat/worker/vision tests; live qwen3:0.6b OFF (`reasoning=0`, final present, stop) and ON (`reasoning=422 chars`, final present, stop).
- Issues: local qwen3:4b manifest ignores native/soft/hard OFF and emits deliberation as content; this model-specific live blocker cannot be safely repaired by text heuristics. Two unrelated ASR pipeline tests fail independently when run alone and were not modified.
- Next action: add SQLite/settings migration, validated independent budgets, compatibility cap metadata, and persisted reasoning.

### 2026-08-13 — Stage 2 budgets and persistence

- Stage: 2 completed; Stage 3 started.
- Completed: independent settings schema/API validation, legacy `max_tokens` migration, one-pass combined/output-only policy metadata, reasoning column and 200k explicit cap, streaming/non-streaming persistence, lightweight history flag, profile-owned reasoning endpoint, and task response redaction.
- Changed: `app/config.py`, `app/db.py`, `app/routes/profiles.py`, `app/schemas/core.py`, chat routes/service/tasks, and focused tests.
- Validation: diff check, compileall, 67 focused settings/migration/lifecycle/API tests; clean and legacy SQLite paths included.
- Issues: no Stage 2 regression; existing ASR/model-manifest findings remain.
- Next action: add LLM budget controls and accessible lazy-loaded reasoning modal/icon in active UI.

## Validation results

- Static checks: baseline passed.
- Unit/contract tests: Stage 1 focused set passed 62 tests after changes.
- Stage 2 unit/contract tests: 67 focused tests passed, including settings validation, legacy migration, profile isolation, storage cap, and both worker modes.
- Integration/smoke tests: native qwen3:4b audit exposed an incompatible OFF manifest; adapter ON/OFF acceptance passed on installed qwen3:0.6b with `keep_alive=0`.
- Manual/regression checks: pending implementation.
- Skipped checks: full Python suite and browser/UI matrix deferred to Stage 5; no changes exist yet.
- Remaining uncertainty: exact combined safety cap/defaults must be reconciled with existing config ranges and context limits during Stage 2.

## Regressions and deferred work

- New regressions: none.
- Pre-existing failures: `test_full_analysis_skips_cleaner_by_default_and_sanitizes_speakers` and `test_pipeline_tasks_are_normalized_for_transcript_record` fail in isolated ASR pipeline runs; they are outside changed chat runtime paths and will be rechecked during full-suite validation.
- Unresolved blockers: none.
- Deferred/technical debt: local `qwen3:4b` must be refreshed/replaced with an Ollama manifest that honors Thinking OFF; adapter continues to send the correct explicit native boolean and Qwen instruction.

## Checkpoints

### Stage 1

- Commit hash: `a74fb46`.
- Message: `feat(chat): separate Ollama reasoning from final output`.
- Files: runtime/service/task separation, focused tests, and this progress state.
- Validation: diff/compile/JS checks, 62 focused tests, live qwen3:0.6b ON/OFF.

### Stage 2

- Commit hash: pending creation.
- Message: `feat(chat): persist reasoning and separate token budgets`.
- Files: settings/schema/routes/runtime policy/task persistence and focused tests.
- Validation: diff/compile checks and 67 focused tests.

## Continuation state

- Current stage: Stage 3 — reasoning and settings UI.
- Last completed action: Stage 2 focused validation; checkpoint preparation.
- Current repository state: Stage 1 committed; validated Stage 2 diff plus progress update pending commit.
- Known risks: modal focus/Escape behavior and mobile action density.
- Next exact action: create Stage 2 checkpoint, then add static UI contract tests before HTML/JS/CSS changes.
- Next files: `web_ui/gui_html.html`, `web_ui/js/app.js`, `web_ui/css/style.css`, focused Node UI test.

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
