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
- Git checkpoint: `32d297b` — Audit and pin deployment dependencies.

### Stage 2 — Bootstrap Implementation
- Goal: add an idempotent root bootstrap command with system, project, and verification phases.
- Related files: `tools/bootstrap_localgpt.py`, `bootstrap_localgpt.command`, `bootstrap_localgpt.sh`, `bootstrap_localgpt.bat`, `bootstrap_localgpt.ps1`, `tests/test_bootstrap_dependencies.py`.
- [x] Completed: shared core detects macOS/Linux/Windows and their supported package managers.
- [x] Completed: native launchers provide Terminal/Windows console entry and bootstrap Python when absent.
- [x] Completed: system, project, and final-verification phases with explicit installation confirmations and idempotent presence checks.
- [x] Completed: models, RAG/user data, `.env`, Tailscale Serve/Funnel, and public exposure remain untouched.
- [x] Completed: safe static/unit validation.
- [~] In progress: Stage 2 checkpoint.
- Architectural decisions: platform-specific entry points are thin wrappers; dependency decisions and verification live in one Python core; Caddy, Tailscale, and Node remain opt-in.
- Problems: initial Windows wrapper stayed in cmd; corrected after the checkpoint so `.bat` now opens the PowerShell launcher. Linux launcher now attempts a native terminal emulator when started without a TTY.
- Technical debt: none yet.
- Next steps: run only safe static/unit checks; real installer acceptance is delegated to the user as requested.
- Validation: `py_compile` passed for bootstrap/test; 5 focused unit tests passed before and after launcher correction; `sh -n` and `zsh -n` passed; `git diff --check` passed. PowerShell runtime is unavailable on the macOS host, so `.ps1` execution is delegated to user acceptance. No package installation commands executed by the agent.
- Git checkpoint: `98bca6a` — Add interactive cross-platform bootstrap; corrective launcher checkpoint pending.

### Stage 3 — QA, Documentation & Cleanup
- Goal: validate bootstrap behavior, update affected permanent docs, record completion, and remove this file in a cleanup commit.
- Related files: tests and affected documentation.
- [x] Completed: safe static and isolated unit validation without executing installers.
- [x] Completed: updated affected setup, architecture, testing, dependency, docs index, and changelog documentation.
- [ ] Pending: user-owned clean-machine acceptance on target platforms.
- [ ] Pending: completion entry in `documentation/change-index.md` after acceptance.
- [ ] Pending: final cleanup commit removing this progress file.
- Architectural decisions: no live model download, generation, transcription, or public-network action during QA.
- Problems: PowerShell and clean Windows/Linux/macOS environments are not available in the current macOS workspace; user explicitly owns real installer acceptance.
- Technical debt: none yet.
- Next steps: create documentation checkpoint and hand off the clean-machine acceptance matrix to the user.
- Validation: safe baseline passed: `git diff --check`, Python `compileall`, Node syntax, markdown rendering tests, 5 bootstrap unit tests, `pip check`, `sh -n`, and `zsh -n`. No installer was executed.
- Git checkpoint: pending.

## Overall Status
- Status: awaiting user acceptance.
- Completed: Stage 1 `32d297b`; Stage 2 `98bca6a`; launcher correction `d490aba`; affected permanent documentation drafted.
- In progress: documentation checkpoint and handoff.
- Pending: user clean-machine acceptance, change index, final cleanup.
- Changed files: `app/requirements.txt`, `docs/DEPENDENCIES.md`, `tools/bootstrap_localgpt.py`, four native bootstrap entry points, `tests/test_bootstrap_dependencies.py`, `README.md`, `docs/README.md`, `docs/ARCHITECTURE.md`, `docs/TESTING.md`, `docs/CHANGELOG.md`, and this progress file.
- Known problems: clean-machine/idempotency/startup acceptance remains unexecuted by explicit user request; PowerShell syntax/runtime was not executable on the current macOS host.
- Technical debt: none identified; optional package availability can vary by Linux distribution repository and is reported explicitly by the installer.
- Next action: user runs the documented acceptance matrix and reports results; fix any platform issue, then add `documentation/change-index.md` entry and remove this progress file in the final cleanup commit.
- Latest Git checkpoint: `d490aba` — Launch Windows bootstrap in PowerShell.

## Continuation Prompt
Continue work on `bootstrap-dependencies` using `docs/progress/bootstrap-dependencies-progress.md`. Read the progress file, current Git status, and latest checkpoint commit first. Current status: implementation and safe QA complete, awaiting user clean-machine acceptance. Completed: dependency audit/pins, shared OS-detecting bootstrap, macOS/Linux Terminal and Windows PowerShell entry points, focused tests, safe baseline, permanent docs. Remaining: record user acceptance results, correct any platform issue, append the completion entry to `documentation/change-index.md`, and remove this progress file in the final cleanup commit. Problems/blockers: installers and PowerShell were intentionally not run by the agent; user owns acceptance. Decisions to preserve: confirmations before installs; no model/data/config/network activation; preserve unrelated ASR progress. Latest checkpoint: `d490aba`; documentation checkpoint follows this progress update. Perform next: run the acceptance matrix in `docs/TESTING.md` on the target clean environment and record exact output/results. Update the progress file before and after the next meaningful stage.
