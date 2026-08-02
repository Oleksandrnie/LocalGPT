# Launcher Python fix progress

## Goal

Make the successful setup hand off cleanly to LocalGPT startup on macOS/Linux/Windows.

## Acceptance criteria

- macOS setup wrapper exits cleanly after setup instead of assigning zsh's read-only `status`;
- start launchers prefer the already prepared `venv` interpreter;
- when `venv` is absent, POSIX launchers find supported versioned Python commands before an incompatible system `python3`;
- regression tests cover the launcher contracts;
- relevant checks pass and the completed progress file is removed.

## Evidence and decisions

- The user log shows setup completed with `[OK]`; no dependency installation failure remains.
- `setup/setup_localgpt.command` then fails on `status`, a reserved read-only zsh parameter.
- `start_localgpt.command` selects `/usr/bin/python3` 3.9 before `venv/bin/python` 3.14, causing `str | None` annotation evaluation to fail.
- Fix the launchers rather than weakening the documented Python 3.10+ runtime contract.

## Changed files

- `setup/setup_localgpt.command`: replaced reserved zsh `status` with `setup_exit`;
- `start_localgpt.command` and `.sh`: prefer `venv/bin/python`, then supported versioned Python fallbacks;
- `start_localgpt.bat`: prefer `venv\\Scripts\\python.exe`;
- `tests/test_setup_dependencies.py`: added setup-exit and start-interpreter regression tests;
- `docs/CHANGELOG.md`: recorded the completed launcher handoff fix.
- `README.md` and `docs/knowledge/networking.md`: direct launch examples now use the project venv instead of an ambiguous system `python3`.

## Validation

- zsh syntax checks for setup/start `.command` — passed;
- POSIX shell syntax check for `start_localgpt.sh` — passed;
- `venv/bin/python -m unittest tests.test_setup_dependencies -v` — 12 tests passed;
- `./start_localgpt.command --help` — passed through the project venv without the Python 3.9 annotation error;
- `git diff --check` — passed;
- `venv/bin/python -m py_compile setup/setup_localgpt.py run_localgpt.py tests/test_setup_dependencies.py` — passed;
- `venv/bin/python -m compileall -q app backend tests` — passed;
- `node --check web_ui/js/app.js` — passed;
- `node tests/markdown_rendering.test.mjs` — 2 tests passed.

## Next step

Review and commit the focused fix, then remove this completed progress file.

## Continuation prompt

Continue this launcher handoff fix, preserve user runtime data, validate without starting live model workloads, update this file before the checkpoint commit, then remove it in final cleanup.
