# LocalGPT audit progress

## Scope

Chat/RAG/memory first, then ASR, Vision/OCR and resource usage; agent orchestration only after core flows are stable. Local models run sequentially on the 16 GiB Mac; no downloads without approval. This is local-only execution state.

## Completed

### C1 — completed and committed

Only completed user/assistant pairs enter history and summary; failed, cancelled, partial, active and orphan rows are excluded; recent and compressed turns are disjoint and session-scoped. Commit: `d6b9d28 fix(memory): bound history to completed turns`.

### C2 — completed and approved for checkpoint

RAG diagnostics use a bounded structured evidence manifest. Summary identity includes ordered message snapshot, `mem_turns`, context budget and version. Sync/task parity, follow-up continuity and profile isolation are covered. Deterministic suite: 129/129; Astra review approved. User authorized the focused C2 checkpoint on 2026-10-20. This checkpoint contains chat/RAG implementation, regression tests and affected docs; ASR input-quality work remains a later stage.

## Live model checks

- `qwen2.5:3b-instruct`: live C2 smoke passed; memory and diagnostics confirmed.
- `qwen3:0.6b`: memory passed (`23` recalled); language miss `Рома` vs `Рим`; keep as optional router, not agent planner.
- `qwen2.5:7b-instruct`: baseline passed; full memory capture incomplete.
- `qwen2.5-coder:7b`: memory passed (`52` recalled).
- `qwen3:4b`: seed completed; durable logs show follow-up completion, so earlier interactive timeout was capture-related, not proven backend failure.
- `mistral-nemo:12b`: memory passed (`74` recalled).
- Vision `qwen2.5vl:3b/7b` and ASR remain separate tracks; `embeddinggemma` is only the RAG embedding provider.

## Decisions

The mini-router is optional for manual model selection; retain it for Auto/Smart Router compatibility and possible future agent routing. Astra is used only after user approval; Sol High handles complex audits/implementations, Sol Medium only bounded changes, Luna simple/UI work.

## Current stage

### ASR2 — FIFO task lifecycle completed

Scope: `backend/apps/asr/tasks.py`, deterministic `tests/test_asr_tasks.py` and directly affected backend/provider/testing docs. One active ASR task child, nonterminal FIFO `queued`, queued cancellation/input cleanup, active cancellation retaining its slot until confirmed death, idempotent terminal dispatch, startup/monitor failure cleanup and bulk-cancel barrier. Routes and provider quality/VAD/timeouts/progress/durable recovery/live audio are unchanged.

Status: implemented and documented in the actual checkout after write approval. Async task requests use one child-process slot and FIFO `queued` admission; queued cancellation cleans up without starting a worker; active cancellation retains the slot until the child is confirmed dead; terminal reconciliation is idempotent; start/monitor failures and bulk shutdown do not strand or accidentally start queued work. Repository `AGENTS.md` takes precedence over the generic progress skill: this progress file accompanies the focused checkpoint; do not create or commit a second progress file. This is a process-local queue, not durable recovery or a global scheduler.

Validation: focused ASR lifecycle + whisper.cpp tests passed, 18/18; `git diff --check` passed. The expanded `test_pipeline_memory` run was attempted as a neighbor check (91 tests total including the focused modules) but did not pass: 2 failures and 8 errors. Several are environment restrictions (sandbox denied Ollama localhost calls and log writes); one unrelated `test_full_analysis_skips_cleaner_by_default_and_sanitizes_speakers` assertion also failed. No changed code in that pipeline was part of this stage. The nine deterministic FIFO tests use fake child processes; no model or live transcription was loaded. Residual risks: direct `/transcribe` and other providers bypass this queue; an unkillable child intentionally retains the slot; failed monitor startup with an unkillable child requires status/cancel polling for reconciliation. No durable recovery or descendant process-group guarantees are added.

Checkpoint: this completed ASR2 stage is covered by the focused local commit accompanying this progress record. After that checkpoint, stop until the user starts the next stage.

### Previous stage — MT1

`MT1 cross-device model transfer audit` — completed and committed. Verified import/export portability for Ollama chat/vision/embedding models, faster-whisper, whisper.cpp model assets and Piper voices. Bundles contain only provider-relative model data, import into the destination device's configured roots, reject unsafe/incomplete content and never carry source-machine absolute paths, accounts, drive letters or platform-specific executables.

Goal: prove that models can be moved between LocalGPT installations without binding the bundle to the original checkout or device. In scope: model-transfer inventory/export/import services, manifest/report semantics, focused backend/UI tests and affected permanent documentation. Out of scope: downloading models, transferring application/runtime binaries or promising that a model runtime is compatible across operating systems/architectures.

Completion criterion: all supported provider families have relocation-focused regression coverage; Ollama coverage includes ordinary chat, Vision and embedding tags through the same manifest/blob path; import into different configured roots succeeds; whisper.cpp clearly separates portable weights/CoreML assets from destination-specific CLI/runtime readiness; focused model-transfer tests and static checks pass.

Implementation: manifest validation now requires every model to name its portable files, rejects cross-family/missing/unreferenced payload entries, and import inspection returns destination runtime requirements. The System UI explains before confirmation and after import that model weights move but platform runtimes do not. Relocation coverage exports synthetic provider units from source roots and imports them into different destination roots; Ollama chat, Vision and embedding inventory uses the same adapter. Transfer specification, provider knowledge, testing guidance and changelog were updated.

Validation: focused backend suite — 15/15 passed; model-transfer UI — 5/5 passed; Markdown rendering — 4/4 passed; JS syntax, Python compileall and `git diff --check` passed. Live read-only `/model-transfer/export-preview` reports 15/15 selectable installed units with no blocked entries: 9 Ollama (including `embeddinggemma`, Qwen chat/coder/Vision), 2 whisper.cpp and 4 Piper. No multi-gigabyte production bundle was created and no installed model storage was mutated.

Checkpoint: `a01348b feat(models): verify portable model transfer`. The preceding ASR relocation implementation is `91e7f62 fix(asr): make whisper cpp runtime relocatable`; its permanent changelog follow-up is `a5c5700 docs(asr): record relocatable whisper runtime`.

### Previous stage — ASR1 completed

Confirmed root cause had two layers: the public CLI link was absolute and stale, and the previously built Mach-O binary/libraries retained the old absolute `LC_RPATH`. GGML model, CoreML encoder and Silero VAD were already present.

Goal: restore runtime readiness and make future setup runs create a relocatable link. In scope: runtime symlink, `tools/setup_whisper_cpp_macos.sh`, focused setup regression, ASR readiness/static validation. Out of scope: transcription quality tuning, GigaAM, Chat/RAG changes and commits.

Completion criterion: relative executable symlink resolves in the current checkout; a temporary relocated fixture proves setup-link behavior; focused setup/whisper.cpp tests and static checks pass; readiness reports ready.

Implementation: runtime link now points to `../source/build/bin/whisper-cli`; macOS setup derives a relative target, resets a stale generated CMake cache after relocation, builds with `@loader_path` RPATH, and replaces stale links with `ln -sfn`. A temporary relocated-checkout regression covers link/cache repair. The local binary was rebuilt at the current path; the previous 35 MiB generated build was moved recoverably to `/private/tmp/localgpt-whisper-build-pre-relocation-20260926`. Affected provider/testing/changelog documentation was updated without changing Chat/RAG code.

Validation: `tests.test_setup_dependencies tests.test_whisper_cpp_backend` — 24/24 passed after the final fix; `git diff --check`, compileall, JS syntax and Markdown rendering — passed; actual `whisper-cli --help` exits 0; Mach-O has `@loader_path`; `/health` on port 8001 is OK; `/whisper/models` reports `large-v3` and `large-v3-turbo` ready with runtime/CoreML/VAD installed and no warnings. UI source maps this `ready` state to badge `Готова`; visual refresh remains optional user acceptance. No live audio transcription was run.

## Next action

1. After the user resumes, start ASR3 input-quality checks using the supplied local MP3, verify installed ASR model readiness, then test sequentially without downloads. Add representative silence/no-speech, short, and abrupt-ending samples only if already available.
2. Compare transcription text, empty-input handling, false phrases, and final segments; keep GigaAM deferred unless the user reopens that decision.
3. The optional user-controlled real model-bundle transfer smoke remains separate.

## Known limitations

Lexical evidence trace is a review signal, not semantic proof. ASR long-recording/no-speech, GigaAM, Vision/OCR quality, image generation and thermal measurements remain pending.
