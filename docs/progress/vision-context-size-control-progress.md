# Vision Context Size Control

## Original Task
- Goal: Вывести настройку vision context size из кода в Settings → Vision и реально передавать её в Ollama, чтобы image chat не падал на default context 4096.
- Acceptance criteria: profile-owned setting отображается и сохраняется в Vision tab; backend валидирует значение; native Ollama `/api/chat` получает `options.num_ctx` для vision inference и обычного chat; есть unit/static regression; permanent docs отражают control; progress-файл удалён в final cleanup commit.
- Source request: пользовательская ошибка `request (6383 tokens) exceeds ... context size (4096)` и просьба добавить настройку в интерфейс.

## Task Analysis
- Architecture scope: shared profile runtime settings in `app/config.py`/`app/routes/profiles.py`, Ollama native payload in `backend/apps/chat/services/ollama_runtime.py`, vision worker kwargs in `backend/apps/chat/tasks.py` and active Vision settings UI in `web_ui/gui_html.html` + `web_ui/js/app.js`.
- Affected areas/files: profile setting normalization/defaults, direct and streaming Ollama options, Vision tab control/save/reset, vision settings tests/UI contract, provider/UI/testing documentation.
- Constraints and risks: preserve profile isolation; keep image binary transient; avoid changing unrelated model settings semantics; bound context size to Ollama/Qwen supported range and make memory tradeoff visible; do not auto-load or rerun live models during tests.

## Documentation Impact Review
- Outcome: Required.
- Documents to update: `docs/knowledge/providers.md` for Ollama `num_ctx` behavior, `docs/knowledge/ui.md` for Vision control, `docs/TESTING.md` for regression/live guidance, `docs/CHANGELOG.md` for completed change. `README.md` and architecture overview remain accurate after the existing multimodal update.
- Project convention: completed-task index is `docs/CHANGELOG.md`; do not create `documentation/change-index.md`.

## Implementation Stages

### Stage 1 — Contract and Runtime Boundary
- Goal: Add validated profile-owned `vision_num_ctx`, default and native Ollama payload support for direct/streaming chat.
- Related files: `app/config.py`, `app/routes/profiles.py`, `app/db.py`, `backend/apps/chat/service.py`, `backend/apps/chat/services/ollama_runtime.py`, `backend/apps/chat/tasks.py`.
- [x] Completed: Added profile-owned `vision_num_ctx` validation/default and native Ollama `options.num_ctx` support for normal and direct vision calls.
- [x] Completed: focused runtime tests.
- Architectural decisions: Use separate `vision_num_ctx` rather than silently replacing general model `num_ctx`; apply it to direct vision analysis/generation, while text-only fallback response keeps normal `num_ctx`.
- Problems: Current runtime did not put `num_ctx` into native Ollama options, so Ollama fell back to 4096 despite configured model settings; fix is implemented, live retry remains user-controlled.
- Technical debt: None known.
- Next steps: checkpoint implementation and complete terminal cleanup.
- Validation: native payload and setting contract tests passed as part of the focused suite.
- Git checkpoint: pending.

### Stage 2 — Vision Settings UI and Regression
- Goal: Add context-size input with safe range, help text, save/reset wiring and static/unit coverage.
- Related files: `web_ui/gui_html.html`, `web_ui/js/app.js`, `tests/test_vision_settings.py`, `tests/chat_attachments_ui.test.mjs`.
- [x] Completed: Added Vision context token input, help text, save/reset wiring and static/unit coverage.
- [x] Completed: run regression and review docs.
- Architectural decisions: Show 4096–131072 tokens, default 8192; recommend 8192 for current M1 Pro/16 GB smoke and warn that larger values increase memory use.
- Problems: None known.
- Technical debt: None known.
- Next steps: checkpoint implementation and complete terminal cleanup.
- Validation: `git diff --check`, compileall, JS syntax and Node UI contract passed; focused Python suite — 86 tests passed.
- Git checkpoint: pending.

### Stage 3 — Documentation, QA and Cleanup
- Goal: Update permanent docs, run proportional static/unit regression, create checkpoint and remove this progress file.
- Related files: `docs/knowledge/providers.md`, `docs/knowledge/ui.md`, `docs/TESTING.md`, `docs/CHANGELOG.md`, this progress file.
- [x] Completed: updated provider/UI/testing documentation and changelog with context-size contract and recovery guidance.
- [~] In progress: checkpoint and cleanup.
- Architectural decisions: No live inference in regression; user can run a bounded live retry after saving 8192 or 16384.
- Problems: Existing unrelated ASR pipeline-memory failures remain known baseline.
- Technical debt: None known.
- Next steps: create implementation checkpoint, then remove this progress file in terminal cleanup commit.
- Validation: static baseline passed; Vision/UI/model/attachment/RAG regression — 86 Python tests passed; Node UI/static checks passed.
- Git checkpoint: pending.

## Overall Status
- Status: cleanup pending
- Completed: runtime contract, Vision UI, focused regression and documentation.
- In progress: checkpoint and cleanup.
- Pending: terminal cleanup commit and final clean status.
- Changed files: `app/config.py`, `app/routes/profiles.py`, `app/db.py`, `backend/apps/chat/service.py`, `backend/apps/chat/services/ollama_runtime.py`, `backend/apps/chat/tasks.py`, `web_ui/gui_html.html`, `web_ui/js/app.js`, tests, affected docs and this progress file.
- Known problems: live retry with the new setting remains pending user-controlled testing; existing unrelated ASR pipeline-memory failures remain baseline.
- Technical debt: None known.
- Next action: review staged diff, commit implementation/docs, then remove this progress file.
- Latest Git checkpoint: `bb7c209` — Remove completed vision progress tracker.

## Continuation Prompt
Continue work on `vision-context-size-control` using `docs/progress/vision-context-size-control-progress.md`. Read the progress file, current Git status and latest checkpoint first. Add profile-owned `vision_num_ctx`, pass it as Ollama native `options.num_ctx` for direct vision inference/streaming, expose it in Vision settings, test it, update affected docs, checkpoint, then remove this progress file in a final cleanup commit. Preserve unrelated user changes and `docs/progress/asr-analysis-modes-progress.md`.
