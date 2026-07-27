# Model Export and Import

## Original Task
- Goal: add a simple Settings → System workflow that exports selected locally installed models into one transferable file and imports that file in another LocalGPT profile.
- Current acceptance criteria:
  - export lists complete Ollama, faster-whisper, whisper.cpp, and Piper units and supports individual/all selection;
  - one uncompressed ZIP64 `.localgpt-models` downloads through the browser;
  - import uses the browser file picker, validates every payload size/SHA-256, previews contents, and requires a separate confirmation;
  - target paths come only from current `config.MODEL_PATHS`;
  - corrupt/unsafe bundles and differing existing targets do not change model storage;
  - identical files are skipped, Ollama blobs publish before manifests, and existing models are never deleted;
  - active UI provides progress, cancellation, concrete errors, and refreshes provider inventory;
  - automated tests use synthetic temporary files only; real model export/import runs only after explicit user action.
- Superseded requirements: external-volume discovery, destination path APIs, exFAT/FAT32 policy, Shared model drive, bundle-directory format, and resume across an interrupted browser transfer are excluded.
- Source: user-approved simplification of `docs/MODEL_TRANSFER_SPEC.md`; progress governed by LocalGPT `AGENTS.md` and the explicitly invoked `temporary-progress-tracking` skill.

## Task Analysis
- Architecture scope: feature mini-app `backend/apps/model_transfer/`, router registration in `backend/server.py`, active UI in `web_ui/gui_html.html` / `web_ui/js/app.js` / `web_ui/css/style.css`, targeted tests, then affected permanent docs.
- Storage boundaries: Ollama → `MODEL_PATHS.ollama`; faster-whisper → `MODEL_PATHS.whisper`; whisper.cpp → `MODEL_PATHS.whisper_cpp`; Piper → `MODEL_PATHS.piper`.
- Security/integrity: no browser-supplied filesystem paths; strict POSIX archive entries below `payload/`; bounded manifest; case-insensitive uniqueness; no symlinks/executables/partial artifacts; complete conflict preflight before writes; server-owned upload/import staging only.
- Atomicity: package-wide rollback is not promised; preflight prevents known conflicts before writes; each file is copied to backend staging, rehashed, and atomically replaced; Ollama manifest entries publish last.
- Constraints/risks: current task registries and uploads are process-local; browser upload is spooled to disk; post-import provider discovery and durable task reconciliation remain to implement; no heavy/live model operations during development.

## Documentation Impact Review
- Outcome: Required
- Update after implementation: `README.md` only if overview becomes incomplete; `docs/ARCHITECTURE.md`; `docs/knowledge/backend.md`; `docs/knowledge/providers.md`; `docs/knowledge/ui.md`; `docs/TESTING.md`; `docs/CHANGELOG.md`; final status/contract cleanup in `docs/MODEL_TRANSFER_SPEC.md`.
- Project override: do not create `documentation/change-index.md`; LocalGPT owns completed significant records in `docs/CHANGELOG.md` and forbids an unrelated documentation tree.

## Implementation Stages

### Stage 1 — Bundle Contract and Inventory
- Goal: strict bundle v1 contract, configured-path inventory, unique-size preview, and feature router.
- [x] Implemented strict manifest parser, path/family/version/hash validation, configured provider inventory, partial rejection, and Ollama shared-blob size deduplication.
- [x] Added `GET /model-transfer/export-preview`.
- Validation: 6 targeted tests, compileall, and `git diff --check` passed.
- Git checkpoint: `31e79d2` — Add model transfer bundle contract.

### Stage 2 — Export and System Settings UI
- Goal: background ZIP64 export and active Settings → System controls.
- [x] Implemented export start/status/cancel/download, ready-only download, temporary archive cleanup, selection UI, progress, download trigger, and import file picker.
- [x] Implemented upload/checksum inspect preview.
- [x] Browser smoke: System tab rendered both buttons; refresh found 12 complete units and showed 28.9 GB unique size; no export was started.
- Validation: 7 targeted tests, JS syntax check, compileall, API/UI smoke, and `git diff --check` passed.
- Git checkpoints:
  - `cc1910e` — Implement model bundle export tasks.
  - `2072be1` — Add model transfer settings UI.

### Stage 3 — Confirmed Import
- Goal: revalidate staged upload, preflight conflicts, publish to configured provider paths, and report/refresh results.
- [x] Implemented server-owned upload retention with opaque `upload_id`.
- [x] Implemented second validation on confirm, provider-root mapping, full conflict preflight, identical-file skip, staged copy/hash, atomic file publication, and Ollama manifest-last ordering.
- [x] Corrected export manifest so every selected model references shared deduplicated files.
- [x] Implemented explicit accessible confirmation UI, apply endpoint, provider inventory refresh after success, concrete imported/skipped report, and cancellation before storage mutation.
- [x] Added staged-upload discard endpoint and cleanup test.
- [x] Added synthetic clean import, identical reimport, target conflict/no-overwrite, and upload discard tests.
- [x] Completed: focused Stage 3 checkpoint created after staged-diff review.
- Validation: JS syntax check and targeted compileall passed; 10 model-transfer tests passed; `git diff --check` passed. All import tests used temporary synthetic files and patched configured roots.
- Git checkpoint: `4633393` — Implement confirmed model bundle import.

### Stage 4 — QA, Permanent Documentation and Cleanup
- Goal: complete proportional validation, update only affected docs, and remove this temporary file in a terminal cleanup commit.
- [x] Completed: baseline static checks, 10 targeted model-transfer tests, and 2 static UI contract tests.
- [x] Completed: full safe unit suite executed (213 tests); 210 passed and 3 unrelated existing ASR/plugin tests failed identically when rerun in isolation.
- [ ] Pending: desktop/mobile, dark/light, keyboard/focus/error-state UI checks without real export/import.
- [ ] Pending: user-controlled later smoke with real models; do not claim it has run.
- [x] Completed: affected architecture/backend/providers/UI/testing/spec/changelog documents updated.
- [ ] Pending: final cleanup commit removing this progress file while preserving `docs/progress/.gitkeep` and the unrelated active ASR progress file.
- Validation: `git diff --check`, compileall, JS syntax, Markdown/UI Node tests passed; targeted model-transfer Python tests 10/10 passed; full suite 210/213 with isolated unrelated failures:
  - `test_full_analysis_skips_cleaner_by_default_and_sanitizes_speakers` — expected phrase absent;
  - `test_pipeline_tasks_are_normalized_for_transcript_record` — empty tasks list;
  - `test_get_plugin_doc_reads_manifest_doc_only` — temporary DB lacks `app_settings`.
- Git checkpoint: pending documentation/QA checkpoint.

## Overall Status
- Status: in progress
- Completed: current product decisions, bundle contract/inventory, export backend, System Settings export UI, upload inspect, and initial import-apply core.
- In progress: Stage 4 documentation/QA checkpoint.
- Pending: manual mobile/light/keyboard check, later user-controlled real-model smoke, and terminal progress cleanup.
- Current uncommitted files: affected permanent docs, model-transfer UI contract test, and this progress update.
- Known problems: import upload/task state is not durable across backend restart; current apply guarantee is conflict preflight plus atomic file publication rather than all-model transaction rollback. UI refreshes existing provider discovery after success; live runtime readiness is intentionally not exercised in automated tests.
- Next action: create documentation/QA checkpoint, then perform remaining manual UI matrix. Keep progress until user-controlled real-model smoke is either accepted or explicitly deferred.
- Latest Git checkpoint: `4633393` — Implement confirmed model bundle import.

## Continuation Prompt
Continue `model-transfer` from `docs/progress/model-transfer-progress.md`. Read this file, `git status`, and checkpoint `2072be1`. Scope is one browser-downloaded/uploaded uncompressed ZIP64 `.localgpt-models`; do not reintroduce volumes, destination paths, filesystem-format policy, Shared model drive, or real-model tests. Stages 1–2 are checkpointed. Stage 3 implementation and validation are complete but uncommitted: opaque staged upload, confirm-time revalidation, conflict preflight, identical skip, staged hash/copy, configured-root atomic publication, Ollama manifest-last ordering, shared-file manifest correction, explicit UI confirmation/apply, provider refresh, upload discard, and 10 passing targeted tests. Next inspect staged diff and commit Stage 3, record its hash, then perform Stage 4 baseline/full safe tests, affected permanent docs, truthful manual UI checks, and terminal progress cleanup. Preserve `docs/progress/asr-analysis-modes-progress.md`.
