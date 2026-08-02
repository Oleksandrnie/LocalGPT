# Direct Python launch progress

## Goal

Restore `python3 run_localgpt.py` as a compatible entry point without downgrading dependencies or changing the macOS system Python.

## Acceptance criteria

- an interpreter older than Python 3.10 re-executes `run_localgpt.py` through the prepared runtime `venv`;
- if no runtime venv exists, a compatible versioned Python command may bootstrap it;
- absence of any compatible interpreter produces an explicit error;
- both direct Python and platform launcher smoke checks pass;
- regression coverage and affected documentation are updated.

## Evidence and decision

- `/usr/bin/python3` is Python 3.9 and evaluates `str | None` before current launcher logic can run;
- current pinned FastAPI, Uvicorn, Hugging Face Hub, and Pillow require Python 3.10+;
- retain Python 3.10+ for the application and turn the old interpreter into a thin bootstrap hop to `venv`.

## Changed files

- `run_localgpt.py`: postponed annotation evaluation and added early compatible-interpreter re-exec;
- `tests/test_setup_dependencies.py`: added a subprocess regression for `python3 run_localgpt.py --help`;
- `README.md`, `docs/ARCHITECTURE.md`, and `docs/CHANGELOG.md`: documented the supported bootstrap handoff.

## Validation

- host `python3 --version` confirms Python 3.9.6;
- `python3 run_localgpt.py --help` — passed and reported handoff to `venv/bin/python`;
- `venv/bin/python -m unittest tests.test_setup_dependencies -v` — 13 tests passed;
- `venv/bin/python -m py_compile run_localgpt.py tests/test_setup_dependencies.py` — passed;
- `./start_localgpt.command --help` — passed;
- `git diff --check` — passed;
- `venv/bin/python -m compileall -q app backend tests run_localgpt.py` — passed;
- zsh/sh syntax checks for the affected launchers — passed;
- `node --check web_ui/js/app.js` — passed;
- `node tests/markdown_rendering.test.mjs` — 2 tests passed.

## Next step

Review the staged diff, commit the fix, then remove this completed progress file.

## Continuation prompt

Continue the direct Python launch compatibility fix, validate without live model workloads, update this progress record before the checkpoint commit, and remove it after completion.
