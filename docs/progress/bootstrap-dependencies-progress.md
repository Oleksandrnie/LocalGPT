# Bootstrap Dependencies

## Original Task
- Goal: enable a new computer to install every non-model dependency required to start LocalGPT by running one bootstrap script.
- Acceptance criteria: complete dependency audit; documented required dependencies and environment variables; root bootstrap script installs missing supported dependencies, reports progress/errors, skips satisfied components, and is safe to rerun; setup documentation is current; validation covers a maximally clean environment without downloading LLM/ASR/TTS models or user data.
- Source ТЗ or request: user-provided Russian specification dated 2026-08-02.

## Task Analysis
- Architecture scope: backend, static frontend, networking, providers, plugins, RAG, launch/build scripts, and project documentation.
- Affected areas/files: dependency manifests; launchers; root bootstrap entry point; setup and subsystem documentation; focused bootstrap tests.
- Constraints and risks: preserve the active `docs/progress/asr-analysis-modes-progress.md`; do not install or select models; do not configure users or migrate data; avoid public networking changes; keep platform/package-manager behavior explicit; distinguish core startup dependencies from feature-conditional tools; do not hide unsupported or failed installations.
- Working assumption: support the repository's existing macOS, Linux, and Windows launcher surfaces through one shared OS-detecting core plus thin native terminal entry points. Automatic system-package installation is limited to detected supported package managers, with actionable failure messages elsewhere.

## Documentation Impact Review
- Outcome: Required.
- Documents to update: `README.md` for first-run workflow; `docs/ARCHITECTURE.md` if launcher/bootstrap responsibilities change; `docs/TESTING.md` for bootstrap validation; affected `docs/knowledge/*.md` files where dependency contracts are incomplete; `docs/CHANGELOG.md` for the completed setup feature; `documentation/change-index.md` as required by the selected progress-tracking skill.

## Implementation Stages

### Stage 1 — Dependency Audit & Contract
- Goal: derive a verified dependency inventory and bootstrap contract from code, manifests, launchers, configuration, and tests.
- Related files: `app/requirements.txt`, `.env.example`, `run_localgpt.py`, launch scripts, `backend/`, `app/`, `plugins/`, `tools/`, documentation.
- [x] Completed: inventoried imports, subprocess/CLI boundaries, runtime versions, package managers, environment variables, and existing automatic setup.
- [x] Completed: added the audited dependency contract in `docs/DEPENDENCIES.md`.
- [x] Completed: pinned direct Python requirements to the verified project environment.
- Architectural decisions: dependency categories will distinguish core, feature-conditional, and access-mode-conditional requirements; model artifacts remain excluded.
- Problems: user explicitly owns clean-machine acceptance; automated external installation must not be run by the agent.
- Technical debt: none identified in the dependency contract; exact package availability still depends on the detected OS repository/package manager.
- Next steps: validate the audit diff and create the Stage 1 checkpoint.
- Validation: source/config/import/subprocess inventory completed; installed host versions and Python package set recorded; `git diff --check` passed; `venv/bin/python -m pip check` passed.
- Git checkpoint: pending.

### Stage 2 — Bootstrap Implementation
- Goal: add an idempotent root bootstrap command with system, project, and verification phases.
- Related files: pending after Stage 1 contract.
- [ ] Pending: implementation.
- Architectural decisions: pending audit.
- Problems: none yet.
- Technical debt: none yet.
- Next steps: implement after Stage 1 checkpoint.
- Validation: pending.
- Git checkpoint: pending.

### Stage 3 — QA, Documentation & Cleanup
- Goal: validate bootstrap behavior, update affected permanent docs, record completion, and remove this file in a cleanup commit.
- Related files: tests and affected documentation.
- [ ] Pending: validation on host plus isolated/dry-run simulations.
- [ ] Pending: documentation and change index.
- [ ] Pending: final cleanup commit removing this progress file.
- Architectural decisions: no live model download, generation, transcription, or public-network action during QA.
- Problems: clean physical machines may be unavailable; use isolated environments and deterministic mocks where necessary, and report that limitation precisely.
- Technical debt: none yet.
- Next steps: begin after implementation checkpoint.
- Validation: pending.
- Git checkpoint: pending.

## Overall Status
- Status: in progress.
- Completed: acceptance criteria extraction; branch/status check; mandatory documentation review; dependency audit and documented contract.
- In progress: Stage 1 validation/checkpoint.
- Pending: audit contract, bootstrap implementation, QA, permanent documentation, change index, cleanup.
- Changed files: `app/requirements.txt`, `docs/DEPENDENCIES.md`, `docs/progress/bootstrap-dependencies-progress.md`.
- Known problems: none.
- Technical debt: pending audit.
- Next action: validate and commit Stage 1, then implement the cross-platform interactive bootstrap core and native entry points.
- Latest Git checkpoint: none.

## Continuation Prompt
Continue work on `bootstrap-dependencies` using `docs/progress/bootstrap-dependencies-progress.md`. Read the progress file, current Git status, and latest checkpoint commit first. Current status: Stage 1 dependency audit ready for checkpoint. Completed: acceptance criteria, mandatory docs, source/config audit, dependency contract and pinned direct requirements. Remaining: cross-platform interactive bootstrap, safe static validation, permanent docs, change index, cleanup. Problems/blockers: user owns real clean-machine acceptance. Decisions to preserve: no model/data/config installation; shared OS-detecting core with macOS/Linux/Windows terminal entry points; categorize core vs conditional dependencies; prompt before installations; preserve unrelated ASR progress. Latest checkpoint: none. Perform next: validate and commit Stage 1, then implement bootstrap. Update the progress file before and after the next meaningful stage.
