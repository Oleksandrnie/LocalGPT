# LocalGPT audit progress

## Scope

ASR input quality, then Chat/RAG model comparison, Vision/OCR, Mac resource control and optional real model-bundle transfer acceptance. GigaAM, agent orchestration and image generation remain deferred. Local models run sequentially on the 16 GiB Mac; no downloads without approval. This active execution record is tracked in stage checkpoints as required by the repository `AGENTS.md`.

## Completed

### C1 — completed and committed

Only completed user/assistant pairs enter history and summary; failed, cancelled, partial, active and orphan rows are excluded; recent and compressed turns are disjoint and session-scoped. Commit: `d6b9d28 fix(memory): bound history to completed turns`.

### C2 — completed and approved for checkpoint

RAG diagnostics use a bounded structured evidence manifest. Summary identity includes ordered message snapshot, `mem_turns`, context budget and version. Sync/task parity, follow-up continuity and profile isolation are covered. Deterministic suite: 129/129; Astra review approved. User authorized the focused C2 checkpoint on 2026-10-20. This checkpoint contains chat/RAG implementation, regression tests and affected docs; ASR input-quality work remains a later stage.

## Live model checks

- `qwen2.5:3b-instruct`: live C2 smoke passed; memory and diagnostics confirmed.
- `qwen3:0.6b`: memory passed (`23` recalled); language miss `Рома` vs `Рим`; keep as optional router, not agent planner.
- `qwen2.5:7b-instruct`: completed-turn memory probe passed; controlled clean RAG run recorded below.
- `qwen2.5-coder:7b`: memory passed (`52` recalled).
- `qwen3:4b`: seed completed; durable logs show follow-up completion, so earlier interactive timeout was capture-related, not proven backend failure.
- `mistral-nemo:12b`: memory passed (`74` recalled).
- Vision `qwen2.5vl:3b/7b` and ASR remain separate tracks; `embeddinggemma` is only the RAG embedding provider.

## Decisions

The mini-router is optional for manual model selection; retain it for Auto/Smart Router compatibility and possible future agent routing. For this audit, GPT-6 Luna with xHigh effort handles reasoning, evidence synthesis and test-result analysis; GPT-6.1 Sol with Medium effort makes architecture and technical-design decisions. Implementation model is selected per stage from the user's explicit instruction. Astra review requires explicit user approval; GPT-6.1 Sol High may substitute only with approval. Workflow conflict resolved by repository authority: `AGENTS.md` requires progress checkpoints to be tracked, overriding the generic skill's local-only progress rule; this existing active file is retained, with no duplicate created.

### DOC1 — model-routing policy and plan alignment (completed)

Updated `AGENTS.md` and this permanent plan with the user-selected analysis/architecture roles, Astra approval boundary and the approved order of remaining work. Marked GigaAM, agent modes and image generation deferred. C1/C2 checkpoint status now matches Git history.

Validation: `git diff --check` passed; `node tests/markdown_rendering.test.mjs` passed 4/4. No code or live-model tests were applicable or run. Checkpoint: `3516bfb docs(plan): update multimodal audit routing`.

## Completed live stage — ASR3

### ASR3 — live ASR input-quality smoke (completed; accuracy score pending reference)

Completed first live baseline on a user-provided Russian MP3 through the user's LocalGPT backend at `127.0.0.1:8000`; assistant-created duplicate backend on `8001` was stopped before inference. Audio metadata: about 5:59.8, 8.2 MB, 44.1 kHz stereo, 192 kbps. Used installed `large-v3-turbo`, Russian language, automatic prompt preset, and `store_result=false`; no downloads and no transcript-history record.

Result: task completed in about 41 seconds; 39 segments, 3,792 characters / 663 whitespace-delimited words. First segment starts at 0.00s; last ends at 359.81s, close to the 359.84s source duration. No known subtitle-credit phrase was detected. This is a lifecycle/coverage baseline, not a measured accuracy score: no reference transcript or word-error comparison was available. Informal inspection suggests likely proper-name and disfluency errors; speaker-role labeling also needs independent validation. Temperature and memory were not measured.

Additional sequential live checks, all on the same `large-v3-turbo` / `whisper_cpp` / Russian / automatic-prompt setup, with `store_result=false`:

- 8-second excerpt from the supplied MP3: completed, 3 segments, timestamps 0.07–8.00s.
- 10.5-second crop ending during speech: completed, 2 segments, timestamps 0.07–10.53s; no task failure at the clipped end.
- Same 10.5-second crop mixed with synthetic low-level pink noise: completed, 2 segments; recognized wording broadly matched the clean crop, with punctuation/segmentation differences. This is not a real-world noise benchmark.
- 10-second digital silence: returned `empty_transcription`, with no transcript record.

Each task returned `stored=false` and `transcript_id=null`, and the task slot returned to idle between cases. No model download occurred. Temporary derived test files were removed. There is no reference transcript for the long MP3, so no WER/CER or objective accuracy claim is available. Memory free percentage was 51% before and 53% after; macOS reported no thermal/performance warning. Numeric temperature and peak per-process memory are still unmeasured and remain in the resource stage.

ASR3 functional smoke is complete for the available samples. The next Chat/RAG audit is documented below.

### Chat/RAG live model comparison — completed for installed target models

Using profile `Clients RAG test` (id 6), I ran one identical CMS/RAG question in fresh, temporary sessions, one model at a time: `qwen2.5:3b-instruct`, clean-session `qwen2.5:7b-instruct`, `qwen3:4b`, `qwen2.5-coder:7b`, and `mistral-nemo:12b`. Each session used RAG and received the same five `rag_third_party.md` chunk IDs (`11506`, `12540`, `10813`, `11684`, `12155`). All five answered with WordPress and Битрикс only; the lexical trace returned `evidence_traceable` (3–5 term overlaps), not a completeness or entailment score. The 7B model separately recalled the exact synthetic memory label `RZ-7314-Q` from its completed prior turn.

Direct `/rag/search` on the exact CMS query marked retrieval `supported`, even though evidence spans included generic/unrelated text; a closely related phrasing marked `conflict` and surfaced other CMS mentions. This shows diagnostic status depends on query phrasing and that lexical traceability does not measure complete coverage. Do not hard-code CMS names: this is evidence for generic retrieval/facet/relevance and corpus-conflict investigation. One earlier 7B answer from the memory-test session differed and is excluded from the controlled comparison because prior turns confounded the test.

The 0.6B Qwen model remains the optional router, not a target answer model; its prior memory/router check is recorded above. Vision and embedding models were excluded from target Chat/RAG. Qwen3 8B was not installed. No downloads or profile-setting changes occurred; all temporary test sessions were deleted.

Resource signal: qwen3 4B reached about 7.5 GB resident / 18% system-wide memory free; Mistral Nemo 12B reached about 12 GB / 6% free. Models were unloaded between tests and free-memory percentage recovered to 64–80%. macOS reported no thermal warning, but exact temperature and peak per-process memory remain pending in the resource stage. Inference was sequential only.

## Current stage — Vision/OCR quality

Inspect installed Vision runtimes and OCR mode, then test existing screenshots, small text and tables sequentially. Keep Vision and fallback chat provenance distinct, do not change profile settings, and do not download models.

### Previous stage — ASR2 FIFO task lifecycle completed

Scope: `backend/apps/asr/tasks.py`, deterministic `tests/test_asr_tasks.py` and directly affected backend/provider/testing docs. One active ASR task child, nonterminal FIFO `queued`, queued cancellation/input cleanup, active cancellation retaining its slot until confirmed death, idempotent terminal dispatch, startup/monitor failure cleanup and bulk-cancel barrier. Routes and provider quality/VAD/timeouts/progress/durable recovery/live audio are unchanged.

Status: implemented and documented in the actual checkout after write approval. Async task requests use one child-process slot and FIFO `queued` admission; queued cancellation cleans up without starting a worker; active cancellation retains the slot until the child is confirmed dead; terminal reconciliation is idempotent; start/monitor failures and bulk shutdown do not strand or accidentally start queued work. Repository `AGENTS.md` takes precedence over the generic progress skill: this progress file accompanies the focused checkpoint; do not create or commit a second progress file. This is a process-local queue, not durable recovery or a global scheduler.

Validation: focused ASR lifecycle + whisper.cpp tests passed, 18/18; `git diff --check` passed. The expanded `test_pipeline_memory` run was attempted as a neighbor check (91 tests total including the focused modules) but did not pass: 2 failures and 8 errors. Several are environment restrictions (sandbox denied Ollama localhost calls and log writes); one unrelated `test_full_analysis_skips_cleaner_by_default_and_sanitizes_speakers` assertion also failed. No changed code in that pipeline was part of this stage. The nine deterministic FIFO tests use fake child processes; no model or live transcription was loaded. Residual risks: direct `/transcribe` and other providers bypass this queue; an unkillable child intentionally retains the slot; failed monitor startup with an unkillable child requires status/cancel polling for reconciliation. No durable recovery or descendant process-group guarantees are added.

Checkpoint: ASR2 commit `5e0ebce fix(asr): serialize transcription task workers`.

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

1. Continue Vision/OCR quality checks and record exact model/runtime/OCR modes.
2. Measure memory/residency and thermals where observable; verify sequential load/unload.
3. Keep the optional user-controlled real model-bundle transfer smoke separate. Keep GigaAM, agent modes and image generation deferred unless the user reopens those decisions.

## Known limitations

Lexical evidence trace is a review signal, not semantic proof or a completeness metric. ASR accuracy remains unscored without reference text. Vision/OCR quality, image generation and detailed thermal/peak-memory measurements remain pending.
