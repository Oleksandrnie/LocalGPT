# Setup Whisper CLI Progress

## Task

- Goal: make the native `whisper.cpp` CLI a standard LocalGPT setup artifact rather than a later manual ASR action.
- Problem: `WHISPER_BACKEND=whisper_cpp` is the default, but first-time setup installs only build prerequisites and leaves `models/whisper_cpp/bin/whisper-cli` absent.
- Expected result: macOS setup builds the executable without downloading a model; setup verifies its presence and documents the platform contract.
- Source specification: user request of 2026-08-03.
- Branch: `codex/rag-source-ingestion`.
- Current stage: Stage 2 — documentation and cleanup.

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

- Status: in progress.
- Update setup/dependency docs and run proportional validation.
- Checkpoint: `Document standard whisper CLI setup`.
