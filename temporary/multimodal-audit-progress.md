# LocalGPT audit progress

## Scope

ASR input quality, then Chat/RAG model comparison, Vision/OCR, Mac resource control and optional real model-bundle transfer acceptance. GigaAM, agent orchestration and image generation remain deferred. Local models run sequentially on the 16 GiB Mac; the user approved downloading only the Russian Tesseract traineddata needed for the current OCR evaluation (no LLM downloads). This active execution record is tracked in stage checkpoints as required by the repository `AGENTS.md`.

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

## Completed live stage — Vision/OCR screenshot spot checks

On 2026-10-20, used two existing image attachments from the Personal profile's prior “выпиши текст” chat in fresh temporary sessions; profile settings were unchanged and no models were downloaded. With OCR assist Off and no image-RAG request, `qwen2.5vl:7b` returned the visible Russian screenshot text nearly verbatim. The initial task route plan said `vision_context` and listed `qwen2.5:3b-instruct` as the response model, but the completed task's actual `result.model` was `qwen2.5vl:7b`; source inspection confirms the worker switches non-RAG image prompts to direct Vision completion. Treat `result.model` as actual responder provenance. `image_rag_included=false`, and RAG diagnostics were disabled.

A separate direct `qwen2.5vl:3b` test transcribed all visible small mixed Russian/English UI labels exactly, including both occurrences of `Off`. Then generated a temporary synthetic high-contrast table (4 columns × 3 rows) with unique mixed Cyrillic/Latin values; both `qwen2.5vl:3b` and `qwen2.5vl:7b` returned all 12 data cells exactly in the requested JSON structure. This is a controlled clean-table baseline, not evidence for dense, skewed, low-resolution, merged-cell or real-world tables. No user data was used; the generated image and test sessions were removed. No independent expected-transcript file was available for automated character-level scoring on the screenshot tests.

### Dense synthetic-table stress test — complete

On 2026-10-20, generated and visually checked a temporary 2040×1070 high-contrast inventory table: 8 rows × 9 data columns (72 cells), a two-level/grouped header, mixed Latin/Cyrillic look-alike identifiers, arrows, decimal commas, thousands separators, quoted text and notes. Sent the same image and exact extraction prompt through the existing LocalGPT backend, profile Personal (id 4), first to `qwen2.5vl:3b`, then to `qwen2.5vl:7b`; never ran both together. Both task results confirm the requested model was the direct Vision responder. `ocr_assist=off`, `image_rag_requested=false`, `rag_enabled_effective=false`, and no OCR evidence or RAG chunks were used. Profile settings were not changed; the existing temperature was 0.25 and output limit was 512 tokens.

- `qwen2.5vl:3b` returned all 8 rows and 72 body cells. By exact Unicode comparison, 68/72 cell strings matched: four cells contained visually confusable but different Latin/Cyrillic glyphs (`K/К`, `C/С`, `A/А`, `T/Т`); numeric values, remaining text and row/column associations matched. It returned the second-level column labels but omitted the three grouped-header labels.
- `qwen2.5vl:7b` returned 69 of 72 body cells before stopping mid-final row: the price, status and note for row 8 were absent. Four of the emitted cell strings had the same kind of Latin/Cyrillic confusable glyph mismatch, so 65/72 expected body cells were exactly represented. It emitted the three grouped-header labels, but as a malformed/ragged Markdown header rather than preserving a consistent merged-header structure. The LocalGPT task state was `completed` even though the reply was visibly incomplete; the request's configured output cap was 512 tokens. The task result exposed neither generated-token count nor provider stop reason, so the cap is a plausible but unconfirmed cause. This shows that task completion alone is not a completeness guarantee.

The 3B run reported about 4.6 GB resident; the 7B run reached about 7.2 GB and system-wide free memory fell to 12–13%. After explicit unload, `ollama ps` was empty and free memory recovered to 70%; macOS reported no thermal/performance warning. Both temporary sessions and the generated fixture were deleted. Numeric temperature and peak per-process RSS remain unavailable. This controlled synthetic table is not a real-world photo/table benchmark; skew, blur, low resolution, visual noise and OCR-assisted Russian remain untested. No model or language data was downloaded, no product code changed, and no profile settings were altered.

Tesseract 5.5.3 exposes only `eng`, `osd`, and `snum` traineddata; Russian is unavailable. A local `eng`-only pass on the mixed-language small-text screenshot returned no text. Russian OCR and OCR-assisted modes therefore remain unvalidated; no language model was installed. The 7B run reached about 7.2 GB resident, then free memory recovered to about 81%; the 3B run reached about 4.6 GB, then recovered to about 77%. macOS reported no thermal/performance warning, while numeric temperature and peak per-process RSS remain unmeasured. Test sessions were deleted and `ollama ps` was empty after each run.

Vision/OCR spot checks now include screenshots, small text, a clean table and a dense grouped-header synthetic table. This closes the controlled synthetic-table test, not real-world table coverage. The main findings are mixed-script glyph confusions in both Vision models and the 7B response truncating under the current 512-token output limit. Russian Tesseract assistance and a real-world table/photo remain open. No profile settings, repository code, or model assets changed.

## Completed live stage — Mac resource/lifecycle smoke

On 2026-10-20, with no Ollama model resident and system-wide free memory around 79%, ran short sequential generation checks on installed models only. `qwen2.5:3b-instruct` returned `ГОТОВО`; `ollama ps` showed about 2.2 GB resident and free memory fell to 66%. Explicit `keep_alive=0` cleared the resident model and memory recovered to 78%. Next `qwen3:4b` reached about 3.2 GB resident and free memory fell to 59%; 12-token and 64-token probes consumed their budgets in thinking and returned no final answer, so this counts only as a resource/lifecycle check. Explicit unload cleared `ollama ps`; free memory recovered to 75%. No models ran concurrently. In the later Vision table comparison, `qwen2.5vl:7b` reached about 7.3 GB and 17% free memory; explicit unload cleared `ollama ps` and free memory recovered to 72% without a macOS thermal/performance warning.

`pmset -g therm` reported no thermal or performance warning. Numeric temperature and peak per-process RSS were not available from the inspected macOS/Ollama interfaces. Swap use was about 4.02 GB at baseline and 3.98 GB afterward; do not attribute this system-level change to model inference. Previous comparison remains recorded: Mistral Nemo 12B reached about 12 GB resident / 6% free memory before unload and recovery. No download or settings change occurred.

The bounded resource/lifecycle smoke is complete; sustained-load temperature and peak-process-memory measurements remain a limitation, not a claim of safe long-running thermals.

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

## Completed follow-up — Vision output/table/OCR and ASR reference

On 2026-10-20, finished the user-approved bounded evaluation and implementation, running local inference sequentially:

- Dense-table cap diagnosis: direct `qwen2.5vl:7b` on the 72-cell clean table ended at `done_reason=length`, exactly 512 tokens, with the old cap. At 1024 it stopped normally after 551 tokens and returned all cells; 2048 returned the same output. Exact strings: 66/72. On a downscaled, slightly rotated/blurred/JPEG-compressed variant, 1024 tokens returned all 72 cells after 397 tokens, also 66/72 exact. Main residuals: four `Оплачен` → `Оплачено` and two Latin/Cyrillic `A/А` confusions.
- Implemented profile-only `vision_output_tokens` (0 inherits ordinary `output_tokens`, explicit 128–8192). Provider stop reason/token count are retained in stream and non-stream paths; a length-truncated direct answer or derived Vision context is rejected instead of marked complete. The ordinary chat limit/default is unchanged. Backend coverage: 52 focused tests passed; attachment/settings UI: 6/6; Python compileall and `git diff --check` passed.
- Installed official Tesseract Russian traineddata locally only (`rus.traineddata`, about 3.7 MB; not in repository). Dense table OCR against a 482-character normalized reference: clean `rus+eng` PSM 6 CER 91.7%, PSM 11 5.8%; photo-like PSM 6 56.6%, PSM 11 42.3%. PSM 11 omitted quantity cells and lost row/column structure; `/ocr/extract` default PSM 6 returned only fragments. No app defaults changed.
- ASR ground truth: used 9 known-transcript WAVs from the held-out Langswap Dialogs `test` split (about 91 seconds total; stems `part1_{53,71,87,101,103,122,165,166,347}`), sequentially through existing `/transcribe`, `large-v3-turbo` / `whisper_cpp`, `language=ru`, `store_result=false`. Aggregate normalized WER 2.3% (4/172 words), CER 0.7% (6/909 characters); normalization lowercases, maps ё→е and strips punctuation/space. One absent test audio file was replaced with another from the same split. This is a small clean scripted-dialog smoke, not a proxy for the user's long/noisy audio; possible model-training overlap cannot be excluded. No transcript rows were saved and the whole dataset was not downloaded.
- No model profile/default was changed; no LLM model downloaded. Ollama runtime is empty after the Vision sequence. Russian traineddata is an OS-level local dependency from this evaluation, not a repository/model asset.

Checkpoint: focused Vision output-completeness feature, associated Vision/OCR findings, and ASR reference metrics are included in this stage's checkpoint.

## Active follow-up — Vision output budget default

### Stage — default 1024 and legacy-profile compatibility

- Goal: make 1024 the default Vision output budget, including profiles that still store legacy `0`, and tell users not to lower it for image extraction. Preserve explicit per-profile values and keep text-only chat limits unchanged.
- Status: completed; awaiting the user's browser acceptance.
- Scope: `app/config.py`, profile settings normalization, Vision runtime budget resolution, Settings → Vision UI, focused tests, `docs/knowledge/providers.md`, `docs/knowledge/ui.md`, `docs/MULTIMODAL_AUDIT_PLAN.md`, and `docs/CHANGELOG.md`.
- Baseline: `vision_output_tokens=0` currently inherits ordinary `output_tokens`; the Personal profile was last recorded at `0`, so it may still use 512. On the tested dense 72-cell fixture, Vision 7B ended at 512 with `done_reason=length`; 1024 completed all 72 cells (66 exact). This prevents a known truncation case but does not guarantee exact recognition or compensate for an image missing from the current request.
- Decision: default and legacy `0` resolve to 1024; explicit allowed values remain available, but the UI recommends not going below 1024. Do not mutate the user's SQLite profile data or initiate a live inference during implementation.
- Validation: `venv/bin/python -m unittest tests.test_vision_settings tests.test_chat_vision_runtime tests.test_chat_attachments tests.test_chat_vision_context tests.test_chat_vision_lifecycle tests.test_vision_rag -v` — 56 passed; `node --test tests/chat_attachments_ui.test.mjs` — 7 passed; `node tests/markdown_rendering.test.mjs` — 4 passed; Python compileall, `node --check web_ui/js/app.js`, and `git diff --check` passed. Only pre-existing FastAPI/httpx and `datetime.utcnow` deprecation warnings appeared. No live Ollama inference or SQLite profile edit.
- Completion criterion: implementation, tests, permanent docs and this progress record agree; focused checks pass; a single scoped checkpoint is created; then stop for the user's browser acceptance.
- Next exact action: create the focused checkpoint, then ask the user to refresh and run a new test with the image attached in the same message.
- Changed files: `app/config.py`, `app/db.py`, `app/routes/profiles.py`, `backend/apps/chat/tasks.py`, `web_ui/gui_html.html`, `web_ui/js/app.js`, `tests/test_vision_settings.py`, `tests/test_chat_vision_runtime.py`, `tests/chat_attachments_ui.test.mjs`, `docs/knowledge/providers.md`, `docs/knowledge/ui.md`, `docs/MULTIMODAL_AUDIT_PLAN.md`, `docs/CHANGELOG.md`, and this progress record.
- Checkpoint: pending; proposed message `fix(vision): default output budget to 1024`.

## Next action

Only user-dependent acceptance remains:

1. After checkpoint, refresh LocalGPT and confirm Settings → Vision displays 1024. Start a fresh test message, attach the screenshot again, and put the extraction instruction in that same message. The previous image-only turn is not reused automatically by direct Vision.
2. If useful, test a genuinely photographed table/receipt after redacting personal data. Current “photo-like” fixture is generated and does not prove camera-photo accuracy.
3. For a domain-specific ASR score on the user's 5:59.8 MP3, create a human reference for a 30–60 second excerpt. A Whisper draft can speed correction, but must be checked against the audio by a person; no second model is ground truth.
4. Optional actual model-bundle transfer to another device, if one is available.

GigaAM, agent modes and image generation remain deferred unless reopened by the user.

## Known limitations

The public ASR sample is only 9 short studio-recorded scripted utterances; it does not assess noisy/overlapping speech, diarization, long-form drift or the user's specific vocabulary. Synthetic Vision/OCR fixtures do not establish real camera-photo accuracy. Tesseract flatten-text CER does not measure cell/row association; the tested sparse-text mode still omitted quantity values. Vision still confuses visually similar Latin/Cyrillic glyphs and status wording; do not normalize these automatically. Numeric temperature and peak per-process memory remain unavailable. Lexical RAG trace remains a review signal, not semantic proof. Image generation is deferred.
