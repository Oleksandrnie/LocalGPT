# Safe Local Model Transfer

## Original Task
- Goal: implement the agreed `docs/MODEL_TRANSFER_SPEC.md` for safe export/import of complete Ollama, faster-whisper, whisper.cpp, and Piper model artifacts between independent LocalGPT profiles through external storage.
- Acceptance criteria: satisfy all ten criteria in `docs/MODEL_TRANSFER_SPEC.md`, including byte-level integrity, provider-unit atomic publication, idempotence, safe path handling, persisted/recoverable tasks, loopback/admin-token protection, and an accessible active Web UI flow.
- Source ТЗ or request: `docs/MODEL_TRANSFER_SPEC.md` (identical to the supplied `MODEL_TRANSFER_SPEC.md` attachment) plus explicit use of the `temporary-progress-tracking` skill.

## Task Analysis
- Architecture scope: new feature mini-app under `backend/apps/model_transfer/`; composition-only router registration in `backend/server.py`; shared SQLite migration/repository integration through the current `app/db.py` boundary; coordination with existing Ollama, ASR, and TTS discovery/task lifecycle; active static UI in `web_ui/gui_html.html`, `web_ui/js/app.js`, and `web_ui/css/style.css`.
- Affected areas/files: model path configuration in `app/config.py`; install-state semantics in `app/services/models.py`; ASR discovery in `backend/apps/asr/downloads.py` and `backend/apps/asr/whisper_cpp.py`; Piper discovery in `backend/apps/tts/providers/piper_provider.py` and service layer; model pull/delete/prepare/preload/voice download coordination; SQLite schema; feature routes/services/repositories/schemas/platform adapters; active Settings UI; targeted tests and affected permanent docs.
- Constraints and risks: preserve profile-specific configured model paths; expose a dry browser download/upload workflow without backend destination-path or volume APIs; use a single uncompressed ZIP64 container with `.localgpt-models` extension; reject traversal/duplicate paths/partial or executable artifacts; avoid leaking source paths or secrets; publish Ollama manifests and other provider units only after required files validate; do not delete existing models/shared blobs; bound archive metadata and stream/spool large payloads without loading models into browser or backend memory; no live heavy model workload without explicit intent.
- Current Git context: branch `models_export_and_import`, clean at analysis start, two local commits ahead of `origin/models_export_and_import`: `3a9593d` and `2619842`; those commits add and clean up the agreed specification only.
- Governing progress convention: use `docs/progress/` from `AGENTS.md`; preserve `docs/progress/.gitkeep`; keep `docs/progress/asr-analysis-modes-progress.md` untouched. The project has no `documentation/` tree and uses `docs/CHANGELOG.md` for completed significant changes, so do not introduce `documentation/change-index.md` contrary to LocalGPT documentation ownership.

## Documentation Impact Review
- Outcome: Required
- Documents to update / reason: `README.md` if the new user-facing feature changes the overview; `docs/ARCHITECTURE.md` for the new feature/data flow and storage boundary; `docs/knowledge/backend.md` for router/task/repository contracts; `docs/knowledge/providers.md` for transferable provider artifact/discovery rules; `docs/knowledge/networking.md` for loopback/admin-token authorization; `docs/knowledge/ui.md` for the Models → Transfer flow; `docs/TESTING.md` for targeted and platform/manual checks; `docs/CHANGELOG.md` for the completed significant change; `docs/MODEL_TRANSFER_SPEC.md` to change its implementation status and record resolved open decisions. Re-check exact affected set after implementation and update only documents made incomplete or inaccurate.

## Implementation Stages

### Stage 1 — Contract and Read-only Inventory
- Goal: establish strict bundle/task contracts, security primitives, persisted task schema/lock policy, and provider inventory/preview without write actions.
- Related files: `backend/apps/model_transfer/`, `backend/server.py`, `app/db.py`, provider discovery/service boundaries, `tests/test_model_transfer_*.py`.
- [x] Completed: read supplied ТЗ, branch/status, local specification commits, `AGENTS.md`, `docs/README.md`, `docs/ARCHITECTURE.md`, `docs/knowledge/backend.md`, `docs/knowledge/providers.md`, `docs/knowledge/networking.md`, `docs/knowledge/ui.md`, and `docs/TESTING.md`.
- [x] Completed: locate configured provider paths, active provider discovery entry points, model task entry points, active UI entry points, progress ignore rules, and the unrelated active ASR progress file.
- [x] Completed: final UX decision supersedes destination-folder handling — export is a browser download and import is a browser file selection/upload; LocalGPT does not discover volumes or accept destination paths.
- [x] Completed: Shared model drive is excluded entirely from the task rather than retained as an implementation follow-up.
- [x] Completed: filesystem-format policy is excluded; no exFAT/FAT32 gating or product concern is required.
- [x] Completed: container decision — one uncompressed ZIP64 file with `.localgpt-models` extension.
- [x] Completed: folder-selection contract removed from scope; the browser owns save/open dialogs.
- [x] Completed: use byte-valid import with a clear runtime validation warning when Ollama is unavailable; never claim runtime-ready until existing provider discovery confirms it.
- [x] Completed: implement strict manifest v1 parser, bounded JSON size, safe POSIX payload paths, case-fold uniqueness, SHA-256 validation helper, and supported-family validation.
- [x] Completed: implement configured-path read-only inventory for Ollama, active ASR backend, whisper.cpp assets, and Piper voice pairs, including partial rejection and shared-file size deduplication.
- [x] Completed: register `GET /model-transfer/export-preview` through the feature router and revise the permanent ТЗ to the confirmed browser ZIP64 workflow.
- [ ] Pending: task persistence/reconciliation and process-wide transfer coordination move to Stage 2 with write actions.
- [x] Completed: test valid/invalid manifests, traversal/case-fold collisions, unsupported versions, partial Ollama, shared blobs, and unique-size plan.
- Architectural decisions: feature logic remains in `backend/apps/model_transfer/`; existing provider discovery semantics are reused rather than reimplemented in the browser; no source changes begin until the open decisions are confirmed.
- Problems: browser download/upload of very large archives requires streaming/spooled I/O and explicit size/free-space handling; archive-level resume after a disconnected transfer is not promised by the simplified UX.
- Technical debt: current model/ASR/TTS task registries are separate and process-local; transfer coordination needs a narrow shared boundary without broad unrelated refactoring.
- Next steps: create Stage 1 checkpoint, then implement streamed ZIP64 export task/download.
- Validation: `venv/bin/python -m unittest tests.test_model_transfer_manifest tests.test_model_transfer_inventory -v` (6 passed); targeted `compileall` passed; `git diff --check` passed.
- Git checkpoint: `31e79d2` — Add model transfer bundle contract; validation: 6 targeted tests, compileall, and diff check passed; changed tracked files: model-transfer contract/inventory/router, server registration, targeted tests, revised ТЗ, and progress record.

### Stage 2 — Safe Export
- Goal: implement removable-volume allowlisting, streamed hash/copy, incomplete bundle journal, resume/cancel/report, final manifest/READY publication, export endpoints, and export UI.
- Related files: `backend/apps/model_transfer/`, `backend/server.py`, `web_ui/gui_html.html`, `web_ui/js/app.js`, `web_ui/css/style.css`, model task coordination points, targeted tests.
- [x] Completed: implement background uncompressed ZIP64 export task, SHA-256 manifest, unique payload entries, status/cancel endpoints, and ready-only download endpoint.
- [ ] Pending: add System Settings selection/progress/download UI and stronger interruption/cleanup/task-persistence coverage.
- [ ] Pending: implement exact provider artifact export, Ollama blob deduplication, free-space reserve, streamed SHA-256, resumable incomplete bundle, cancellation, and error mapping.
- [ ] Pending: add export preview/task UI and targeted backend/static UI tests.
- Architectural decisions: source model artifacts remain immutable; browser download destination and subsequent transport are outside LocalGPT; the archive contains strict manifest/checksums and provider payload only.
- Problems: platform-specific discovery and eject behavior require test doubles plus later real-device checks.
- Technical debt: none recorded yet.
- Next steps: start only after Stage 1 validation/checkpoint.
- Validation: `venv/bin/python -m unittest tests.test_model_transfer_manifest tests.test_model_transfer_inventory tests.test_model_transfer_export -v` (7 passed); targeted compileall and `git diff --check` passed; tests used temporary synthetic bytes only.
- Git checkpoint: pending backend-export checkpoint.

### Stage 3 — Safe Import
- Goal: implement read-only bundle inspect, explicit confirmation/conflict choices, staged provider-unit publication, post-import discovery validation, recovery, and import UI.
- Related files: `backend/apps/model_transfer/`, provider discovery/runtime boundaries, active Web UI, targeted tests.
- [ ] Pending: validate READY/schema/path/file inventory and hashes without writes to model storage.
- [ ] Pending: implement idempotent staged copy, Ollama blobs-before-manifest publication, atomic ASR/Piper units, explicit tag replacement, and no-overwrite defaults.
- [ ] Pending: implement provider post-import validation, task recovery/reporting, UI refresh, and targeted tests.
- Architectural decisions: package-wide atomicity is not claimed; discoverable model-unit atomicity is required.
- Problems: runtime validation result semantics depend on the unresolved Ollama decision.
- Technical debt: none recorded yet.
- Next steps: start only after Stage 2 validation/checkpoint.
- Validation: pending.
- Git checkpoint: pending.

### Stage 4 — QA, Documentation and Cleanup
- Goal: run proportionate automated/manual verification, update only affected permanent documentation, record deferred platform checks truthfully, remove temporary artifacts, and create the final cleanup commit.
- Related files: targeted tests, active UI, affected docs listed in the documentation-impact review, this progress file.
- [ ] Pending: baseline static checks, targeted model-transfer/provider tests, full safe unit suite when useful, API smoke, and UI contract checks.
- [ ] Pending: manual desktop/mobile, dark/light, keyboard/focus/error-state checks; real macOS/Windows removable-volume checks only where suitable hardware/environments are available.
- [ ] Pending: update affected permanent docs and remove this completed progress file in a separate final cleanup commit.
- Architectural decisions: Shared model drive is explicitly excluded and must not be designed or implemented as part of this task.
- Problems: current workspace is macOS; Windows and physical exFAT/APFS/NTFS/FAT32/eject checks may remain external validation blockers rather than being falsely reported as passed.
- Technical debt: none recorded yet.
- Next steps: start after Stage 3 checkpoint.
- Validation: pending.
- Git checkpoint: pending.

## Overall Status
- Status: in progress
- Completed: decisions, revised contract, Stage 1 manifest/inventory/preview implementation and targeted validation.
- In progress: Stage 2 export backend checkpoint, then System Settings UI.
- Pending: all implementation, validation, permanent documentation updates, checkpoint commits, and final cleanup.
- Changed files: `backend/apps/model_transfer/__init__.py`, `manifest.py`, `inventory.py`, `router.py`, `backend/server.py`, two targeted test modules, `docs/MODEL_TRANSFER_SPEC.md`, and this progress file.
- Known problems: simplified single-file browser transfer drops the original external-volume resume workflow; large-file streaming and temporary-space behavior must be explicit and tested.
- Technical debt: separate provider task registries will require carefully scoped coordination.
- Next action: commit export backend, record hash, then add System Settings export/import surface.
- Latest Git checkpoint: `31e79d2` — Add model transfer bundle contract.

## Continuation Prompt
Continue work on `model-transfer` using `docs/progress/model-transfer-progress.md`. Read the progress file, current Git status, `docs/MODEL_TRANSFER_SPEC.md`, and latest checkpoint commit first. Current status: Stage 1 in progress; no source implementation has started yet. Completed: required analysis/docs review and final product decisions. Confirmed UX: System Settings contains adjacent export/import actions; export selects individual/all complete models and downloads one uncompressed ZIP64 `.localgpt-models` file; import chooses that file through the browser and uploads it for validation/application. Explicitly excluded: backend destination paths, volume/removable-drive discovery, filesystem-format policy, exFAT/FAT32 concerns, Shared model drive, and transport-method ownership. Remaining: revise the ТЗ and complete Stages 1–4 with validation, focused checkpoint commits, affected documentation, and final progress cleanup. Preserve configured provider paths, strict archive validation, provider-unit atomicity, discovery-based readiness, streamed/spooled I/O, and no live heavy workloads by default. Latest checkpoint: `2619842`. Perform next: revise `docs/MODEL_TRANSFER_SPEC.md`, implement Stage 1 contract/inventory/tests, validate, explicitly add this ignored file with `git add -f`, inspect the staged diff, and create the Stage 1 checkpoint. Update the progress file before and after the next meaningful stage.
