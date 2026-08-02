# Portable setup fix progress

## Goal

Restore the cross-platform first-time setup introduced by PR #43 and consolidate all setup entry points under `setup/`.

## Acceptance criteria

- macOS, Linux, and Windows setup entry points live in `setup/` beside their implementation and README;
- every entry point resolves the repository root correctly regardless of the caller's working directory;
- setup installs the canonical `app/requirements.txt` into the runtime `venv/` used by `run_localgpt.py`;
- documentation gives one unambiguous platform command and explains that `.venv/` is not the runtime environment;
- tests cover entry-point locations, portable path resolution, canonical requirements, and runtime venv alignment;
- relevant static and unit checks pass without invoking package installers or live model workloads;
- user-owned untracked `.venv/` remains untouched.

## Scope

- `setup/` launchers and setup core;
- setup dependency tests;
- setup, architecture, dependency, testing, root usage, and changelog documentation made inaccurate by the move.

## Risks

- moving double-click launchers can break relative paths on all three operating systems;
- Windows quoting and PowerShell argument forwarding cannot be executed natively on macOS;
- package installation must not be triggered during automated validation.

## Stages

1. Audit PR #43, attached terminal transcript, current entry points, docs, and tests.
2. Move launchers and make repository-root resolution explicit.
3. Add regression coverage and update affected documentation.
4. Run static/unit/safe verification checks.
5. Commit implementation, remove this completed progress file in cleanup, and report results.

## Decisions

- The attached transcript shows manual `pip install -r requirements.txt` failing because the canonical file is `app/requirements.txt`; the corrected manual install succeeds.
- The transcript's `.venv/` is separate from LocalGPT's canonical `venv/`, so it does not satisfy the launcher/runtime contract.
- All five setup-owned files (`.command`, `.sh`, `.bat`, `.ps1`, `.py`) belong under `setup/`; root start launchers remain in place.
- Existing `.venv/` is user-owned and will not be removed or modified.

## Changed files

- moved `setup_localgpt.command`, `.sh`, and `.bat` from the root into `setup/`;
- updated `setup/setup_localgpt.ps1` to locate the Python core through `$PSScriptRoot`;
- updated `setup/setup_localgpt.py` to distinguish and preserve a manually created `.venv/`;
- expanded `tests/test_setup_dependencies.py` with layout, executable-bit, canonical-path, versioned-Python, and `.venv/` regression coverage;
- updated `README.md`, `setup/README.md`, architecture, dependencies, testing, and changelog documentation.

## Validation

- `python3.12 -m py_compile setup/setup_localgpt.py tests/test_setup_dependencies.py` — passed;
- `python3.12 -m unittest tests.test_setup_dependencies -v` — 9 tests passed;
- `/bin/sh -n setup/setup_localgpt.sh` — passed;
- `/bin/zsh -n setup/setup_localgpt.command` — passed;
- running `setup/setup_localgpt.sh --verify-only` from `/tmp` — passed and resolved the correct project root/runtime `venv/`;
- `git diff --check` — passed;
- `venv/bin/python -m compileall -q app backend tests` — passed;
- `node --check web_ui/js/app.js` — passed;
- `node tests/markdown_rendering.test.mjs` — 2 tests passed;
- `venv/bin/python -m unittest tests.test_setup_dependencies -v` — 9 tests passed.

## Problems and deferred work

- `gh` is unavailable locally; PR #43 identity and patch were resolved from merge commit `347ab39` and its first-parent diff.
- First portable shell smoke exposed the main PR regression: the launcher ignored an installed `python3.12` because it only searched `python3`/`python`; versioned Python 3.10–3.13 commands are now checked first.
- Moving the shell launchers initially lost executable bits; permissions were restored and are now asserted by tests.
- Windows launcher execution cannot be exercised natively on this macOS host; path/quoting changes are covered by source inspection and Python tests, with clean-Windows acceptance still required.

## Next step

Review the staged diff and create the implementation checkpoint commit.

## Continuation prompt

Continue the portable setup fix from this file. Preserve `.venv/`, inspect the current diff/status, complete the next pending stage, validate without live installers/models, and update this record before each checkpoint commit.
