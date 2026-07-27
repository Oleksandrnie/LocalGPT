# Ollama pull API compatibility

## Original Task
- Goal: diagnose the actual Ollama executable/runtime used by LocalGPT and safely fix model-download progress when a CLI rejects `--json`.
- Acceptance criteria: identify command origin and runtime path; collect local macOS diagnostics; replace incompatible pull flow with a compatible streamed API flow where safe; improve diagnostics; cover compatibility and failure paths with tests; run relevant checks without dependency mass-upgrades.
- Source ТЗ or request: user request of 2026-07-27.

## Task Analysis
- Architecture scope: launcher (`run_localgpt.py`), model lifecycle (`app/services/models.py`, `app/routes/models.py`), configured Ollama HTTP endpoint, UI download state, model-install tests.
- Affected areas/files: `app/services/models.py`, routes/tests and provider/testing documentation if the external behavior changes.
- Constraints and risks: preserve configured remote/local endpoints and existing CLI fallback; never load or pull a model during validation; report an unavailable CLI/server distinctly; do not modify dependencies.

## Documentation Impact Review
- Outcome: Required.
- Documents to update: `docs/knowledge/providers.md` for the pull transport/compatibility contract; `docs/TESTING.md` if a targeted Ollama download test command needs documenting; `docs/CHANGELOG.md` for the completed behavioral fix.

## Implementation Stages

### Stage 1 — Analysis & Foundation
- Goal: trace all Ollama invocation paths, examine real local runtime/CLI/API, and establish the compatibility design.
- Related files: `run_localgpt.py`, `app/services/models.py`, `app/routes/models.py`, tests, launch configuration.
- [x] Completed: source and environment inspection.
- [x] Completed: confirmed diagnosis and implementation decision.
- Architectural decisions: use native `POST /api/pull` stream as the default; use `ollama pull <model>` without `--json` only when `/api/pull` is unavailable; do not infer CLI age from a missing unsupported flag.
- Problems: full unrelated suite has two deterministic `test_pipeline_memory` failures and one suite-order SQLite error in `test_plugin_registry`; isolated plugin test passes.
- Technical debt: none recorded.
- Next steps: review the implementation, complete docs and final QA.
- Validation: required macOS commands run; Homebrew CLI `/opt/homebrew/bin/ollama` 0.32.4 and server `/api/version` 0.32.4 confirmed; `ollama pull --help` confirms no `--json`; `/api/ps` reports no loaded models.
- Git checkpoint: not needed (research only).

### Stage 2 — Core Implementation
- Goal: implement the smallest compatible progress path with actionable logging and tests.
- Related files: pending analysis.
- [x] Completed: HTTP streaming pull, error diagnostics, CLI compatibility fallback and cancellation support implemented.
- [x] Completed: unit coverage added for streamed progress, no-`--json` CLI fallback, absent binary/unavailable server and stderr reporting.
- Architectural decisions: HTTP pull cancels by closing the stream; native API cannot pause an in-flight request, so the existing pause endpoint returns an explicit 409 instead of pretending to pause it.
- Problems: CLI fallback retains full stdout/stderr diagnostics but cannot expose incremental textual progress; the normal HTTP transport provides incremental progress.
- Technical debt: none in scope.
- Next steps: create the implementation checkpoint with this progress file.
- Validation: `tests.test_ollama_pull`, `test_model_install_state`, and `test_chat_vision_runtime` pass; `compileall`, `git diff --check`, `node --check`, and markdown rendering tests pass. `mypy`/`ruff` and a build manifest are not present, so no typecheck/lint/build command is configured.
- Git checkpoint: pending.

### Stage 3 — QA, Documentation & Cleanup
- Goal: run proportional verification, update only affected permanent docs, and remove this temporary progress record in a cleanup commit.
- Related files: tests and affected documentation.
- [~] In progress: permanent documentation and final validation complete; cleanup remains.
- Architectural decisions: no dependency upgrades or live model pull performed.
- Problems: full suite result must be reported with the exact unrelated failures if they remain after final checks.
- Technical debt: none in scope.
- Next steps: commit implementation, then cleanup the progress file in a final documentation commit.
- Validation: full suite ran 203 tests: 1 failure and 2 errors outside this change; isolated two pipeline failures reproduce, isolated plugin test passes.
- Git checkpoint: pending.

## Overall Status
- Status: in progress
- Completed: diagnosis, implementation, focused tests, initial documentation update.
- In progress: implementation checkpoint.
- Pending: stage checkpoint, final cleanup commit.
- Changed files: `app/services/models.py`, `tests/test_ollama_pull.py`, `docs/knowledge/providers.md`, `docs/TESTING.md`, `docs/CHANGELOG.md`, `docs/progress/ollama-pull-api-progress.md`.
- Known problems: full suite pre-existing/out-of-scope pipeline tests fail; none in the Ollama pull path.
- Technical debt: none.
- Next action: stage and commit the implementation checkpoint, then remove this progress file in the final cleanup commit.
- Latest Git checkpoint: pending implementation checkpoint.

## Continuation Prompt
Continue work on `ollama-pull-api` using `docs/progress/ollama-pull-api-progress.md`. Read the progress file, current Git status, and latest checkpoint commit first. Current status: implementation and QA complete, checkpoint pending. Completed: Homebrew Ollama 0.32.4 at `/opt/homebrew/bin/ollama` and local `/api/version` verified; root cause traced to `ollama pull --json`; HTTP pull transport, CLI compatibility fallback, logging, tests and permanent docs added; focused tests and static checks pass. Remaining: commit implementation, then remove this file in final cleanup. Problems/blockers: full suite has two reproducible unrelated pipeline failures and one suite-order plugin SQLite error. Decisions to preserve: no dependency mass updates, no live pull, API-first transport, CLI fallback without `--json`. Latest checkpoint: pending. Perform next: create the implementation checkpoint with this progress file, then create cleanup commit.
