# Model Transfer Specification

## Original Task
- Goal: подготовить ТЗ для безопасного экспорта и импорта локальных моделей между профилями macOS и Windows без ручного переноса runtime-папок.
- Acceptance criteria: описаны scope, формат пакета, UX, целостность, совместимость, API/UI, тесты, этапы и ограничения.
- Source ТЗ or request: пользователь просит обдумать и написать ТЗ для переноса моделей через внешний диск.

## Task Analysis
- Architecture scope: model storage/configuration, chat/Ollama, ASR/Whisper, TTS/Piper, API и Web UI.
- Affected areas/files: `app/config.py`, `app/services/models.py`, `backend/apps/asr/downloads.py`, `backend/apps/tts/providers/piper_provider.py`, `app/routes/models.py`, `backend/apps/asr/models_routes.py`, `web_ui/js/app.js`, `web_ui/js/models.js`, `docs/`.
- Constraints and risks: Ollama model состоит из manifest и content-addressed blobs; каталоги могут быть переопределены через `.env`; модели велики и обычно уже сжаты; нельзя импортировать partial downloads, profile data или executable code; внешний носитель физически должен вмещать экспорт; volume discovery, drive letters, case sensitivity, ACL/file locking и filesystem limits различаются между macOS и Windows.

## Documentation Impact Review
- Outcome: Required.
- Documents to update: новый постоянный документ `docs/MODEL_TRANSFER_SPEC.md`; `docs/README.md` — ссылка на него; `docs/BACKLOG.md` — незавершённая запланированная feature.

## Implementation Stages

### Stage 1 — Analysis & Foundation
- Goal: сверить ТЗ с фактическими storage boundaries и существующими API.
- Related files: `AGENTS.md`, `docs/README.md`, `docs/ARCHITECTURE.md`, `docs/knowledge/providers.md`, `docs/knowledge/backend.md`, `docs/knowledge/ui.md`, `docs/TESTING.md`, `docs/BACKLOG.md`, model services/routes.
- [x] Completed: проверены ветка и чистый worktree; прочитаны обязательные документы; установлены реальные model paths и provider boundaries.
- [x] Completed: составлена спецификация, уточнён cross-platform scope macOS + Windows и mandatory exFAT transport format.
- [~] In progress: first documentation checkpoint and cleanup.
- Architectural decisions: по умолчанию нужен переносимый bundle-каталог без перекодирования/сжатия на exFAT; архив остаётся опциональной transport-обёрткой; contract поддерживает macOS и Windows через platform-specific volume adapter, а package paths остаются platform-neutral.
- Problems: формат и реализация ещё не существуют.
- Technical debt: none.
- Next steps: create the stage checkpoint.
- Validation: read-only code/document inspection; `git diff --check`; untracked spec whitespace check; required-file and section/requirement checks passed.
- Git checkpoint: pending.

### Stage 2 — Technical Specification
- Goal: зафиксировать контракт, acceptance criteria и implementation plan.
- Related files: `docs/MODEL_TRANSFER_SPEC.md`, `docs/README.md`, `docs/BACKLOG.md`.
- [x] Completed: создан contract v1, UX/API/security requirements, acceptance criteria, staged implementation plan и required Git/progress workflow.
- Architectural decisions: uncompressed portable bundle directory on exFAT; selection supports all complete models or an explicit subset; multiple bundles are permitted, but a single model unit is not split across drives in MVP.
- Problems: none.
- Technical debt: none.
- Next steps: create the documentation checkpoint commit.
- Validation: `git diff --check`, untracked spec whitespace check, required-file checks and section/requirement grep passed.
- Git checkpoint: pending.

### Stage 3 — QA, Documentation & Cleanup
- Goal: проверить ссылки и diff, создать checkpoints, удалить task progress file.
- Related files: `docs/progress/model-transfer-spec-progress.md`, permanent docs.
- [~] In progress: first documentation checkpoint.
- Architectural decisions: pending.
- Problems: none.
- Technical debt: none.
- Next steps: stage task-only documents and commit them.
- Validation: documentation validation passed; Git checkpoint pending.
- Git checkpoint: pending.

## Overall Status
- Status: in progress
- Completed: repository and architecture analysis; permanent cross-platform model-transfer specification; docs index and backlog update.
- In progress: first documentation checkpoint.
- Pending: final cleanup commit removing this temporary progress file.
- Changed files: `docs/MODEL_TRANSFER_SPEC.md`, `docs/README.md`, `docs/BACKLOG.md`, `docs/progress/model-transfer-spec-progress.md`.
- Known problems: none.
- Technical debt: none.
- Next action: stage task-only documentation changes and create the first focused checkpoint.
- Latest Git checkpoint: none.

## Continuation Prompt
Continue work on `model-transfer-spec` using `docs/progress/model-transfer-spec-progress.md`. Read the progress file, current Git status, and latest checkpoint commit first. Current status: first documentation checkpoint. Completed: storage analysis and permanent cross-platform spec, including mandatory exFAT, all-or-selected model export and multiple independent bundles; documentation checks passed. Remaining: create checkpoint, then remove the task progress file in a final cleanup commit. Decisions to preserve: use an uncompressed portable bundle; model families need type-specific validation; no profile data, partial downloads, executables or automatic deletion; do not split one model unit across drives in MVP. Latest checkpoint: none. Perform next: stage the task-only documents and commit them.
