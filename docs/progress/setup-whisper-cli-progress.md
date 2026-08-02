# Setup Whisper CLI Progress

## Task

- Goal: make the native `whisper.cpp` CLI a standard LocalGPT setup artifact rather than a later manual ASR action.
- Problem: `WHISPER_BACKEND=whisper_cpp` is the default, but first-time setup installs only build prerequisites and leaves `models/whisper_cpp/bin/whisper-cli` absent.
- Expected result: macOS setup builds the executable without downloading a model; setup verifies its presence and documents the platform contract.
- Source specification: user request of 2026-08-03.
- Branch: `codex/rag-source-ingestion`.
- Current stage: Stage 2 — completed; ready for final progress cleanup.

## Scope lock

- In scope: macOS setup, the existing macOS whisper.cpp build script, setup tests and affected setup documentation.
- Out of scope: downloading ASR models/CoreML artifacts, silently falling back to faster-whisper, and inventing unverified Windows/Linux build flows.
- Baseline: `setup_localgpt.py` already installs Git/CMake/curl/unzip and checks Apple Command Line Tools, while `tools/setup_whisper_cpp_macos.sh` builds CLI but also downloads model artifacts.
- Unrelated change to preserve: deleted `rag_sources/profile_2_third_party/third_party.templates.json`.

## Stages

### Stage 1 — Build CLI during macOS setup

- Status: completed.
- Add an artifact-free mode to the existing build script, invoke it from macOS setup, and assert setup checks the resulting executable.
- Validation: setup unit tests, shell syntax, and a real macOS build requested by the user. The build created `models/whisper_cpp/bin/whisper-cli`; the ASR runtime status reports CLI, `large-v3-turbo`, and its CoreML encoder ready.
- Checkpoint: `Build whisper CLI during macOS setup`.

### Stage 2 — Documentation and cleanup

- Status: completed.
- Updated setup/dependency, architecture, testing, root README and changelog documentation. Validation passed: setup unit tests (14), shell syntax, Python compilation, UI static check, dictation UI test and Markdown rendering test.
- Checkpoint: `Document standard whisper CLI setup`.

## Changed files

- `setup/setup_localgpt.py`
- `tools/setup_whisper_cpp_macos.sh`
- `tests/test_setup_dependencies.py`
- `README.md`
- `setup/README.md`
- `docs/ARCHITECTURE.md`
- `docs/DEPENDENCIES.md`
- `docs/TESTING.md`
- `docs/CHANGELOG.md`

## Decisions and continuation

- A native CLI belongs to the standard macOS bootstrap because `whisper_cpp` is the default ASR backend; model artifacts remain an explicit user action.
- Linux and Windows do not receive a guessed build flow. Extend those platforms only with a separately verified implementation.
- Next step: remove this completed progress file in the final cleanup commit.
