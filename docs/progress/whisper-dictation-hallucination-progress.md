# Whisper Dictation Hallucination Progress

## Task

- Goal: prevent the default `whisper.cpp` dictation flow from inserting common non-speech hallucinations such as “Thank you.” after short recordings.
- Acceptance criteria: the CLI command uses decoder-level non-speech suppression and does not temperature-fallback into invented text; the behavior is covered by focused tests; user-spoken text is not filtered after recognition.
- Source specification: user report and screenshot, 2026-08-03.
- Branch: `codex/rag-source-ingestion`.
- Current stage: Stage 2 — completed; ready for final progress cleanup.

## Scope lock

- In scope: `whisper.cpp` command defaults and VAD runtime, chat-dictation language/short-recording handling, backend/UI tests, documentation and validation.
- Out of scope: replacing the ASR model, installing a VAD model, forcing Russian language for every dictation, or deleting recognised phrases by a deny-list.
- Confirmed facts: chat dictation sent `language=auto` despite the active profile `ru` preset. Runtime logs showed completed recordings detected as `en` with one 10-character segment. A synthetic 3-second silence input hallucinated text without VAD and returned no segments with VAD.
- Risk: no-speech protection may return an empty result for a recording with too little actual speech. This is preferable to silently inserting fabricated text and is reported to the user as an empty transcription.
- Unrelated change to preserve: deleted `rag_sources/profile_2_third_party/third_party.templates.json`.

## Stages

### Stage 1 — Decoder safeguards

- Status: completed.
- Added profile language propagation, a 700 ms recording guard, decoder safeguards and required Silero VAD. macOS setup now installs VAD with the CLI and verifies it.
- Validation: focused backend/setup tests, UI static tests, shell syntax and a live synthetic-silence smoke using the installed `large-v3-turbo` runtime.
- Checkpoint: `Suppress non-speech whisper hallucinations`.

### Stage 2 — Documentation and cleanup

- Status: completed.
- Updated README, setup README, dependency/testing documentation and changelog. Final validation passed: 21 focused Python tests, 3 static UI tests, shell syntax, Python compilation, JavaScript syntax, and the live synthetic-silence smoke.
- Checkpoint: `Document dictation hallucination safeguards`.

## Decisions and continuation

- Do not suppress a list of phrases after transcription: it can delete real speech. VAD removes non-speech before decoding instead.
- The active profile's `ru`/`en` preset is now also respected by chat dictation; users can change it in ASR Studio.
- The current Mac runtime now contains `ggml-silero-v6.2.0.bin`; restart LocalGPT to load the changed backend code.
- Next step: delete this completed progress file in the final cleanup commit.
