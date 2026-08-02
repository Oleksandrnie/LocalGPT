# Model Transfer Upload Cleanup Progress

## Task

- Goal: prevent inspected model-transfer bundles from accumulating in `app/data/model_transfer/uploads` and let the user clean that storage from Settings → System.
- Expected result: terminal import paths delete their bundle; System shows upload storage usage and offers a confirmed cleanup action.
- Source specification: user request, 2026-08-03.
- Branch: `codex/model-transfer-upload-cleanup`.
- Started: 2026-08-03.
- Current status: active.
- Current stage: Stage 1 — backend upload-storage contract.

## Instructions and precedence

- Direct user requirements: create a separate branch; use `project-progress-workflow`; remove imported archives or offer deletion; add a System settings cleanup control.
- Applicable rules: repository `AGENTS.md` and model-transfer specification require a temporary progress record and focused checkpoint commits.
- Git authorization: branch explicitly authorized; stage commits required by repository workflow.

## Scope lock

### In scope

- Model-transfer upload archive lifecycle and orphan cleanup.
- Read/delete API restricted to the backend-owned upload directory.
- Settings → System UI, confirmation, status and static UI contract tests.

### Out of scope

- Export archive retention, model artifact deletion, scheduled cleanup, or arbitrary filesystem cleanup.

### Affected areas and expected files

- `backend/apps/model_transfer/import_service.py`, `router.py`, transfer tests.
- `web_ui/gui_html.html`, `web_ui/js/app.js`, UI contract test.
- Affected model-transfer UI/backend documentation and changelog if required.

### Risks and rollback concerns

- Cleanup must only delete `.localgpt-models` files directly inside the configured upload directory and must invalidate in-memory upload IDs.
- A cleanup action must be confirmed and keyboard-accessible.

## Baseline

- Current behavior: successful `apply_import`, failed apply, and explicit cancelled confirmation unlink one registered archive. Files left after inspect without confirmation or process restart remain in `DATA_DIR/model_transfer/uploads`.
- Existing tests: `tests.test_model_transfer_import`; `tests/model_transfer_ui.test.mjs`.
- Validation commands: targeted transfer tests, UI static test, baseline static checks.
- Pre-existing failures: none observed; baseline test suite not yet run.
- Branch and working-tree state: started clean from `dev` at `cb74827`.

## Architecture

- Current flow: router streams a selected bundle to the backend-owned uploads folder; an opaque ID maps to its path in process memory; import/discard removes registered paths.
- Target flow: upload service owns a constrained storage summary and explicit cleanup operation; router exposes it; UI requests a confirmed cleanup and refreshes its summary.
- Contracts and boundaries: no client filesystem paths; cleanup is constrained to the configured backend-owned uploads directory.

## Implementation stages

### Stage 1 — Backend upload-storage contract

- Goal: expose safe upload usage and cleanup, including in-memory ID invalidation.
- Status: completed.
- Actions: centralize upload directory resolution; add summary/cleanup service functions and GET/DELETE router endpoints; add unit tests.
- Validation: `venv/bin/python -m unittest tests.test_model_transfer_import -v`.
- Completion criterion: only direct upload bundle files are counted/deleted and registered IDs are invalidated.
- Proposed checkpoint commit: `feat(model-transfer): add upload archive cleanup API`.

### Stage 2 — System settings control

- Goal: make usage visible and let the user confirm cleanup from System settings.
- Status: pending.
- Actions: add markup, UI state/requests, confirmation/accessibility and static contract coverage.
- Validation: `node tests/model_transfer_ui.test.mjs`, syntax check.
- Completion criterion: user can see usage, confirm deletion, and get a precise result without affecting models.
- Proposed checkpoint commit: `feat(ui): add model transfer upload cleanup control`.

### Stage 3 — QA and cleanup

- Goal: complete proportional validation and permanent documentation, then remove this progress record.
- Status: pending.
- Validation: baseline static checks and targeted tests.
- Completion criterion: requirements checked, docs current, clean tree after cleanup commit.
- Proposed checkpoint commit: `docs(model-transfer): document upload archive cleanup`.

## Decisions

### Automatic terminal cleanup plus explicit recovery cleanup

- Context: import already unlinks registered archives in terminal paths, but orphan archives can survive before confirmation or process restart.
- Decision: preserve automatic deletion after import/discard and add an explicit user-confirmed cleanup for remaining backend-owned upload archives.
- Reason: satisfies deletion expectation without risking user model files and gives the user a recovery control for historical residue.

## Progress log

### 2026-08-03 — Analysis complete

- Completed: verified branch state, model-transfer specification, upload/import implementation, Settings System UI and existing tests.
- Next action: implement constrained backend storage summary and cleanup.

### 2026-08-03 — Stage 1 implemented

- Completed: centralized the backend-owned upload directory; added usage summary and constrained cleanup APIs; cleanup removes only direct regular `.localgpt-models` files and invalidates their opaque IDs.
- Changed: `backend/apps/model_transfer/import_service.py`, `backend/apps/model_transfer/router.py`, `tests/test_model_transfer_import.py`.
- Validation: `venv/bin/python -m unittest tests.test_model_transfer_import -v` (4 passed); `git diff --check` passed.
- Next action: inspect staged diff and create Stage 1 checkpoint, then build the System settings control.

## Continuation state

- Current stage: Stage 1.
- Next exact action: stage Stage 1 files and create its focused checkpoint.
