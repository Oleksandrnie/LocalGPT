# Setup Dependencies

## Original Task
- Goal: enable a new computer to install every non-model dependency required to start LocalGPT by running one setup script.
- Acceptance criteria: complete dependency audit; documented required dependencies and environment variables; root setup script installs missing supported dependencies, reports progress/errors, skips satisfied components, and is safe to rerun; setup documentation is current; validation covers a maximally clean environment without downloading LLM/ASR/TTS models or user data.
- Source ТЗ or request: user-provided Russian specification dated 2026-08-02.

## Task Analysis
- Architecture scope: backend, static frontend, networking, providers, plugins, RAG, launch/build scripts, and project documentation.
- Affected areas/files: dependency manifests; launchers; root setup entry point; setup and subsystem documentation; focused setup tests.
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
- Git checkpoint: `32d297b` — Audit and pin deployment dependencies.

### Stage 2 — Bootstrap Implementation
- Goal: add an idempotent root bootstrap command with system, project, and verification phases.
- Related files: `bootstrap/bootstrap_localgpt.py`, `bootstrap/bootstrap_localgpt.ps1`, three root platform entry points, `bootstrap/README.md`, and `tests/test_bootstrap_dependencies.py`.
- [x] Completed: shared core detects macOS/Linux/Windows and their supported package managers.
- [x] Completed: native launchers provide Terminal/Windows console entry and bootstrap Python when absent.
- [x] Completed: system, project, and final-verification phases with explicit installation confirmations and idempotent presence checks.
- [x] Completed: models, RAG/user data, `.env`, Tailscale Serve/Funnel, and public exposure remain untouched.
- [x] Completed: safe static/unit validation.
- [x] Completed: consolidated internal setup implementation into `setup/`, retaining only one user-facing entry point per OS in the project root.
- [x] Completed: renamed user-facing files from `bootstrap_localgpt.*` to `setup_localgpt.*`; retained “bootstrap” only as the technical term in specialist documentation.
- [~] In progress: setup naming/documentation checkpoint.
- Architectural decisions: platform-specific entry points are thin wrappers; dependency decisions and verification live in one Python core; `setup` is the user-facing name, while bootstrap remains the technical term in specialist documentation; Caddy, Tailscale, and Node remain opt-in.
- Problems: initial Windows wrapper stayed in cmd; corrected after the checkpoint so `.bat` now opens the PowerShell launcher. Linux launcher now attempts a native terminal emulator when started without a TTY.
- Technical debt: none yet.
- Next steps: validate renames, then finalize at the user's explicit direction.
- Validation: prior safe checks passed; renamed paths pending the same syntax/unit validation. PowerShell runtime is unavailable on the macOS host. No package installation commands executed by the agent.
- Git checkpoint: `98bca6a` — Add interactive cross-platform bootstrap; corrective launcher checkpoint pending.

### Stage 3 — QA, Documentation & Cleanup
- Goal: validate bootstrap behavior, update affected permanent docs, record completion, and remove this file in a cleanup commit.
- Related files: tests and affected documentation.
- [x] Completed: safe static and isolated unit validation without executing installers.
- [x] Completed: updated affected setup, architecture, testing, dependency, docs index, and changelog documentation.
- [x] Completed: user accepted closure with clean-machine installer acceptance deferred outside this task.
- [ ] Pending: completion entry in `documentation/change-index.md` during cleanup.
- [ ] Pending: final cleanup commit removing this progress file.
- Architectural decisions: no live model download, generation, transcription, or public-network action during QA.
- Problems: PowerShell and clean Windows/Linux/macOS environments are not available in the current macOS workspace; user explicitly accepted closing the task without that external acceptance.
- Technical debt: none yet.
- Next steps: validate renamed paths, create setup-naming checkpoint, then add change index and remove this progress file in final cleanup.
- Validation: safe baseline passed before rename: `git diff --check`, Python `compileall`, Node syntax, markdown rendering tests, 5 setup/bootstrap unit tests, `pip check`, `sh -n`, and `zsh -n`. Renamed-path validation pending. No installer was executed.
- Git checkpoint: `2f9a141` — Document and harden bootstrap workflow.

## Overall Status
- Status: ready for completion.
- Completed: Stage 1 `32d297b`; Stage 2 `98bca6a`; launcher correction `d490aba`; folder consolidation `a527105`; setup naming and documentation updates in progress.
- In progress: renamed-path validation and cleanup checkpoint.
- Pending: completion index and final cleanup only.
- Changed files: `app/requirements.txt`, `docs/DEPENDENCIES.md`, `setup/`, three root native setup entry points, `tests/test_setup_dependencies.py`, `README.md`, `docs/README.md`, `docs/ARCHITECTURE.md`, `docs/TESTING.md`, `docs/CHANGELOG.md`, and this progress file.
- Known problems: clean-machine/idempotency/startup acceptance was not executed; user explicitly accepted closing with that external validation deferred.
- Technical debt: none identified; optional package availability can vary by Linux distribution repository and is reported explicitly by the installer.
- Next action: run safe renamed-path validation, commit setup naming/docs, then add `documentation/change-index.md` entry and remove this progress file in the final cleanup commit.
- Latest Git checkpoint: `2f9a141` — Document and harden bootstrap workflow.

## Continuation Prompt
Continue work on `setup-dependencies` using `docs/progress/setup-dependencies-progress.md`. Read the progress file, current Git status, and latest checkpoint commit first. Current status: ready for completion after the user accepted closure without external clean-machine acceptance. Completed: dependency audit/pins, shared OS-detecting setup, macOS/Linux Terminal and Windows PowerShell entry points, focused tests, safe baseline, permanent docs, and setup naming. Remaining: run renamed-path checks, append the completion entry to `documentation/change-index.md`, and remove this progress file in the final cleanup commit. Problems/blockers: installers and PowerShell were intentionally not run by the agent; user explicitly accepted deferral. Decisions to preserve: confirmations before installs; no model/data/config/network activation; preserve unrelated ASR progress. Latest checkpoint: `a527105`. Perform next: validate renames and close the task.
