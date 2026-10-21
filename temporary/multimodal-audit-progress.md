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

The mini-router is optional for manual model selection; retain it for Auto/Smart Router compatibility and possible future agent routing. Codex model routing and review approval rules have one canonical source: the repository-root `AGENTS.md`; this progress record and permanent plan link to it instead of duplicating model assignments. Workflow conflict resolved by repository authority: `AGENTS.md` requires progress checkpoints to be tracked, overriding the generic skill's local-only progress rule; this existing active file is retained, with no duplicate created.

### DOC1 — model-routing policy and plan alignment (completed)

Established `AGENTS.md` as the canonical source for Codex model routing and review approval; the permanent plan now links to it instead of maintaining a duplicate. Marked GigaAM, agent modes and image generation deferred. C1/C2 checkpoint status now matches Git history.

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
- Status: implementation completed and committed; browser acceptance confirmed the new 1024 default is active, but a dense real table still exceeded the per-call budget. Automatic continuation is now the requested follow-up rather than repeatedly asking the user to raise the setting manually.
- Scope: `app/config.py`, profile settings normalization, Vision runtime budget resolution, Settings → Vision UI, focused tests, `docs/knowledge/providers.md`, `docs/knowledge/ui.md`, `docs/MULTIMODAL_AUDIT_PLAN.md`, and `docs/CHANGELOG.md`.
- Baseline: `vision_output_tokens=0` currently inherits ordinary `output_tokens`; the Personal profile was last recorded at `0`, so it may still use 512. On the tested dense 72-cell fixture, Vision 7B ended at 512 with `done_reason=length`; 1024 completed all 72 cells (66 exact). This prevents a known truncation case but does not guarantee exact recognition or compensate for an image missing from the current request.
- Decision: default and legacy `0` resolve to 1024; explicit allowed values remain available, but the UI recommends not going below 1024. Do not mutate the user's SQLite profile data or initiate a live inference during implementation.
- Validation: `venv/bin/python -m unittest tests.test_vision_settings tests.test_chat_vision_runtime tests.test_chat_attachments tests.test_chat_vision_context tests.test_chat_vision_lifecycle tests.test_vision_rag -v` — 56 passed; `node --test tests/chat_attachments_ui.test.mjs` — 7 passed; `node tests/markdown_rendering.test.mjs` — 4 passed; Python compileall, `node --check web_ui/js/app.js`, and `git diff --check` passed. Only pre-existing FastAPI/httpx and `datetime.utcnow` deprecation warnings appeared. No live Ollama inference or SQLite profile edit.
- Completion criterion: implementation, tests, permanent docs and this progress record agree; focused checks pass; a single scoped checkpoint is created; then stop for the user's browser acceptance.
- Acceptance evidence: the user re-attached the image and repeated the extraction prompt. The backend recorded one attachment (2096×880, about 336 KB), `vision_output_tokens=1024`, and `done_reason=length`; actual responder was direct Vision `qwen2.5vl:3b`, not selected text model `qwen3:4b`. Effective RAG was disabled with zero chunks. No profile/default changes were made during this check.
- Changed files: `app/config.py`, `app/db.py`, `app/routes/profiles.py`, `backend/apps/chat/tasks.py`, `web_ui/gui_html.html`, `web_ui/js/app.js`, `tests/test_vision_settings.py`, `tests/test_chat_vision_runtime.py`, `tests/chat_attachments_ui.test.mjs`, `docs/knowledge/providers.md`, `docs/knowledge/ui.md`, `docs/MULTIMODAL_AUDIT_PLAN.md`, `docs/CHANGELOG.md`, and this progress record.
- Checkpoint: `263ce5f fix(vision): default output budget to 1024`; 14 files, 95 insertions and 27 deletions. Focused validation passed; no live model ran. The local progress file is updated with the verified hash after commit and will be included in the next checkpoint after user acceptance.

## Completed follow-up — bounded automatic continuation on output-limit

- Goal: when Ollama explicitly ends a final-answer generation with `done_reason=length` and provides non-empty answer text, automatically resume from the accumulated text in the same chat task, using the same model, user settings and (when relevant) image evidence. Keep each per-call token budget unchanged; do not silently raise Vision or ordinary chat limits.
- User request: preserve the original task and formatting, continue at the cutoff instead of requiring a manual retry or a larger token setting, and repeat until the provider ends normally.
- Scope: Chat task streaming/non-streaming completion, the direct Vision and Vision→RAG completion legs, shared text completion compatibility path if it remains the same bounded change, tests and relevant provider/architecture/testing/changelog documentation. ASR transcript pipelines, tool execution, semantic completeness detection and frontend redesign are out of scope.
- Decisions/assumptions: retry only explicit `done_reason=length` with non-empty final content; do not retry empty or reasoning-only exhaustion, cancellation, provider errors, or normal stops. Each follow-up carries the prior assistant text and a short instruction to continue without repeating, preserving the original prompt, selected model/settings and explicit-RAG decision. Add exact-overlap de-duplication and a finite safety bound of at most four continuation calls after the first attempt; reaching the bound must remain visibly incomplete and must not enter memory/history as a completed pair. Keep the existing token limit as the per-call cap. The app can detect provider truncation, not whether a normally stopped answer is semantically complete.
- Acceptance criteria: deterministic tests prove multi-part completion on text and direct Vision streams/results; final answer is joined once with no duplicated overlap; ordinary stop makes one call; no-content/reasoning-only, cancellation, provider failure and the safety bound terminate safely; explicit RAG is not newly triggered; profile/session protection and final-output security guard still cover the joined answer; incomplete capped output is never marked complete. No live inference during implementation.
- Stage CONT1 — bounded automatic continuation; implementation and validation complete, focused checkpoint pending. Proposed commit: `feat(chat): continue responses truncated by token limit`.
- Baseline: latest failed UI request confirmed direct Vision `qwen2.5vl:3b` reached its 1024-token per-call output cap; existing task handler rejected the answer and cleared partial content. Branch `feature/prompt-rag-security-hardening`.
- Implementation: shared continuation orchestration is wired to chat text stream/non-stream, direct Vision stream/non-stream, and explicit RAG-vision analysis plus response. It continues only on explicit length exhaustion with nonempty final text, uses the same per-call settings/model/image evidence, preserves the original retrieval decision, removes exact suffix/prefix overlap, and has a hard cap of four extra calls. Continuation exhaustion remains failed/incomplete; privacy checks cover joined output and pass boundaries.
- Documentation and policy: providers, architecture, testing and changelog describe the behavior. `AGENTS.md` is now the sole project source of model routing; the audit plan and progress record link to it. Related custom skill instructions were updated to defer to the target repository's `AGENTS.md` and committed in `personal-knowledge-and-workflows` as `ae94670 docs(skills): centralize model routing in AGENTS`.
- Validation: the implementation agent reports the targeted chat/Vision/RAG suite passed 157 tests across `tests.test_chat_continuation`, `tests.test_model_router`, `tests.test_chat_vision_lifecycle`, `tests.test_chat_vision_runtime`, `tests.test_chat_vision_context`, `tests.test_prompt_rag_security_audit`, `tests.test_chat_memory_boundary`, `tests.test_chat_rag`, and `tests.test_vision_rag` (with explicit `local_hash` embedding overrides). Parent reran `venv/bin/python -m unittest tests.test_chat_continuation -v` — 10/10; `venv/bin/python -m compileall -q app backend tests`, `node --check web_ui/js/app.js`, `node tests/markdown_rendering.test.mjs` — 4/4, and `git diff --check` passed. No live inference, model download, profile mutation or restart.
- Existing unrelated wider-suite failures: `test_full_analysis_skips_cleaner_by_default_and_sanitizes_speakers` and `test_pipeline_tasks_are_normalized_for_transcript_record` in ASR pipeline tests. They were reproduced against original HEAD by the implementation agent; both bypass changed chat completion by patching `ChatService.chat_completion`.
- Changed files: `AGENTS.md`, `backend/apps/chat/service.py`, `backend/apps/chat/tasks.py`, new `backend/apps/chat/services/continuation.py`, new `tests/test_chat_continuation.py`, `docs/ARCHITECTURE.md`, `docs/CHANGELOG.md`, `docs/TESTING.md`, `docs/knowledge/providers.md`, `docs/MULTIMODAL_AUDIT_PLAN.md`, and this progress record.
- Checkpoint: LocalGPT commit `e4fb4f3 feat(chat): continue responses truncated by token limit`. User acceptance is complete: a fresh image-attached prompt completed correctly; a separate follow-up without reattaching the image could not perform image-dependent work, as expected because image bytes are attached to the specific request, not retained as visual context for later messages. No further implementation is required for this stage.

## Active follow-up — broader Chat/RAG, resource measurements, and Ollama LLM installer

The user authorized completing these items without intermediate approvals; provide one final summary for their own acceptance testing. Keep the existing single progress file and checkpoint each non-empty implementation stage. Do not push, restart LocalGPT, mutate profile defaults/history, or download models during implementation. Run all local inference sequentially and unload after each run.

### CHAT-EVAL — cross-domain evidence and answer-completeness evaluation

- Extend the already-completed five-model single-CMS baseline using a compact, domain-independent test matrix; do not repeat the old CMS question.
- Separate (a) whether retrieval selects the expected evidence/facts from (b) whether each model uses all supplied evidence and abstains when facts are absent.
- Use installed text chat models only; `qwen3:0.6b` remains an optional router and Vision/embedding/ASR models are not answer targets. No model downloads.
- Only implement a shared pipeline change if the results expose a repeatable product-level defect, with a generic regression test; do not hard-code corpus vocabulary or optimize to one client RAG.
- Record per-model factual coverage and abstention behavior, identify retrieval vs generation failures, and update permanent plan/changelog as appropriate.

### RESOURCE-MEASURE — sequential local model footprint

- Inspect already available, non-privileged macOS/Ollama signals for peak process memory, system memory pressure, swap deltas and thermal warnings. Do not install measurement utilities or claim numeric temperature when unavailable.
- Measure representative installed Chat models one at a time; explicitly unload between runs. Keep earlier smoke measurements as historical context, not a substitute for the new measurements.
- Record exact signals and limitations; never run local model inference concurrently.

### LLM-INSTALL — self-service Ollama chat model download

- Add a Settings → Chat/LLM installer near the bottom of the LLM panel. It must accept a raw model reference or a narrowly parsed Ollama install snippet, show progress/status inline and reuse the existing pull/cancel lifecycle.
- First scope is Ollama chat LLMs only. Parse and validate references; call the existing configured API/task lifecycle, never execute arbitrary shell or `ollama run`. Reject extra/mismatched commands. The common two-line `ollama pull X` + `ollama run X` snippet may be accepted only by ignoring the run line and communicating that explicitly.
- Preserve explicit download confirmation and manual model selection after download. Validate with mocked/task tests; do not perform an actual model pull or alter runtime/model directories during implementation.
- Add focused UI/backend tests and update provider/UI/testing/backlog/changelog documentation.

### LLM-INSTALL-SELECT — discoverability of downloaded custom chat models

- Status: `completed`; checkpoint commit follows.
- Goal: after a successful pull, any locally installed, non-catalog Ollama chat model becomes visible in the normal model selectors without being auto-selected or started; replace the model-specific placeholder with generic supported syntax.
- Confirmed baseline: `/models` refreshes the installed inventory during download polling, but the selectors and chat library only render configured catalog entries when that catalog is non-empty. Thus arbitrary installed models can be present in `/models.installed` and still be absent from the UI. Pull completion already refreshes `/models`; no runtime restart or model download is needed for implementation validation.
- Scope: active web UI model inventory/selection, a small pure model-list helper and UI tests, `docs/knowledge/ui.md`, `docs/knowledge/providers.md`, `docs/CHANGELOG.md`, and this progress record. Exclude capability guessing beyond excluding confirmed embedding-only models, automatic selection/run, backend pull lifecycle changes, and actual pulls.
- Acceptance: custom installed chat-capable/unknown-capability models absent from chat/utility/Vision catalogs appear in selectors and library; configured catalog entries do not duplicate; utility/Vision and embedding-only entries stay out of the chat selector; fresh list polling exposes them after pull; user must select manually. Placeholder uses generic valid `model:tag` syntax.
- Implementation: added a pure selectable-model builder; ordinary chat selectors, quick picker, chat model library and saved-selection validation now include installed non-catalog models while keeping utility/Vision models in their own lanes and excluding embedding-only models. Replaced the `gpt-oss:20b` placeholder with generic valid `model:tag` syntax. Pull progress polling already refreshes `/models`; after completion the new inventory flows into the selectors. Model remains manually selected and is not started automatically.
- Changed files: `web_ui/js/chat_model_catalog.mjs`, `web_ui/js/app.js`, `web_ui/gui_html.html`, `tests/chat_model_catalog.test.mjs`, `tests/ollama_install_ui.test.mjs`, `docs/knowledge/ui.md`, `docs/knowledge/providers.md`, `docs/TESTING.md`, `docs/CHANGELOG.md`, and this progress record.
- Validation: `node --check web_ui/js/app.js`; full `node --test tests/*.test.mjs` — 41/41; `git diff --check` passed. No browser automation, local model pull, or LocalGPT restart; live UI acceptance remains with the user.
- Checkpoint: `1722e90 fix(models): expose installed custom chat models`.

### LLM-INSTALL-COPY — make the example and helper explicit that `run` is unnecessary

- Status: `completed`; copy-only follow-up to the installer selection stage.
- Goal/result: show only `ollama pull model:tag` in the input placeholder and tell users that `ollama run` is unnecessary; if included in a pasted accepted snippet it is ignored. Clarify that the compatible model appears for manual selection after the pull.
- Validation: `node --check web_ui/js/app.js`; full `node --test tests/*.test.mjs` — 41/41; `git diff --check` passed. No browser/server restart or model pull.
- Checkpoint: `a22eceb fix(ui): clarify Ollama pull-only install example`.

Implementation complete: the Settings → Chat/LLM panel now accepts a bounded raw Ollama model reference, one `ollama pull` line, or that pull plus an exact matching `ollama run` line (which is explicitly ignored). It reuses existing confirmation, pull, status polling and cancellation; the inline panel shows recent pull status/progress, transfer size/ETA and cancellation. Backend validates again before accepting an API request; no shell command is executed and the selected model is not changed. Installer backlog item moved to the completed changelog. No model was downloaded and no app/profile state was changed.

Validation passed: `node --check web_ui/js/app.js`; `node --test tests/ollama_install.test.mjs tests/ollama_install_ui.test.mjs` (6/6); `venv/bin/python -m unittest tests.test_ollama_model_ref_validation tests.test_ollama_pull -v` (7/7); `node tests/markdown_rendering.test.mjs` (4/4); `git diff --check`. UI/runtime acceptance is intentionally left for the user; LocalGPT was not restarted. Checkpoint: `1231bb3 feat(models): add guarded Ollama LLM installer`.

### CHAT-EVAL — cross-domain evidence and answer-completeness evaluation

- Retrieval eval used `hybrid_v2` with an explicit `local_hash-v1` override (no Ollama embedding runtime); 10 synthetic queries / 12 synthetic documents, 8 positive and 2 unsupported. Expected-source/context recall was 7/8 positive cases (87.5%); unsupported queries were rejected 2/2; typo retrieval was 1/2. All 3 paraphrase cases selected the expected source and included it in context, but facet diagnostics returned `not_found` (facet-confirmed rate 0/3). This is a heuristic/status mismatch, not proof retrieval failed.
- Sent the same six synthetic evidence cases sequentially to all five installed target models (`qwen2.5:3b-instruct`, `qwen2.5:7b-instruct`, `qwen3:4b`, `qwen2.5-coder:7b`, `mistral-nemo:12b`). All 30 final answers were non-empty and ended normally; revised lexical markers covered all five positive cases per model, each model abstained on the one unsupported question, and no unsupported color was emitted. These are fixed synthetic examples and lexical coverage markers, not semantic proof or full LocalGPT profile/session RAG tests.
- Found and fixed a post-answer diagnostic bug: `overall_status=not_found` overrode a non-empty prompt evidence manifest and falsely returned `evidence_not_found`. Traceability now uses only actual included manifest content; absence of a manifest remains `evidence_not_found`. Generic regression covers traceable and untraceable outputs when facet status is `not_found`.

### RESOURCE-MEASURE — sequential local model footprint

Measured the five-model direct synthetic test with one-second runner RSS sampling, system free memory and `vm_stat` swapouts; each model was explicitly unloaded. Peak sampled runner RSS / minimum free memory: Qwen2.5 3B 2.1 GB / 52%; Qwen2.5 7B 4.7 GB / 36%; Qwen3 4B 3.4 GB / 42%; Qwen2.5 Coder 7B 4.6 GB / 32%; Mistral Nemo 12B 7.0 GB / 14%. Swapouts were 0 for the first four; Mistral Nemo 12B added 100,796 swapout pages. It took about 25 seconds and unloaded; a later idle snapshot had 83% free memory and empty `ollama ps`. `pmset` reported no thermal/performance warning; numeric temperature is unavailable here and no privileged `powermetrics` was used. RSS is sampled runner-only peak, not a guaranteed maximum or complete app footprint. Avoid concurrent local models; the 12B model caused material pressure/swap.

Qwen3 4B in the same run was requested with `think=False` (`/no_think`) but returned reasoning text and took about 99 seconds across six short prompts. This does not mean Thinking was intentionally on; it means the no-thinking request did not suppress measured reasoning work. Track as a separate toggle/provider investigation.

### Thinking-budget defaults — implemented, acceptance pending

Raised the default `thinking_tokens` allowance to 4096 and enforced a minimum of 2048 in Settings/UI, API validation, effective model settings and runtime policy. Existing low overrides read as 2048 without database migration; Output tokens remains independent; higher manual overrides up to 32768 remain supported. This allowance affects Thinking ON and hybrid-Qwen OFF compatibility paths, not ordinary OFF output-only requests, and is not a guarantee of actual reasoning token consumption.

Validation: 106 focused Python tests passed across model routing, RAG answer quality, live-eval scoring, retrieval eval and Vision runtime, plus the changed pipeline token-budget test; 12 Node UI/Markdown tests passed; compileall, JavaScript syntax and `git diff --check` passed. A broader `tests.test_pipeline_memory` run still has its previously known unrelated ASR-pipeline failures (`test_full_analysis_skips_cleaner_by_default_and_sanitizes_speakers`, `test_pipeline_tasks_are_normalized_for_transcript_record`). No model download, profile/database mutation, LocalGPT restart or parallel inference occurred. User acceptance of the installer and new Thinking-token display remains pending.

Checkpoint: `970ec9f fix(chat): clarify RAG evidence and reasoning budgets`.

### LLM-REASONING-CONTROLS — discover and expose per-model thinking levels

- Status: `completed`; R1–R4 implementation, documentation, and final focused validation are complete. UI/runtime acceptance remains for the user after refreshing/restarting their local app as needed.
- User requirement: newly installed models must expose their actual reasoning controls in model settings and quick model selection, including `low` / `medium` / `high` where supported; this must not be tied to the OpenAI model name or one model catalog.
- Confirmed provider contract: Ollama `/api/show` returns top-level `thinking.values` and `thinking.default`; values are model-specific booleans or exact strings. Ollama `/api/chat` accepts a supported boolean/string in `think`. `gpt-oss` advertises `low`, `medium`, and `high`. Missing metadata is unknown/default behavior, not evidence that all models share those levels.
- Scope: discover/sanitize Ollama thinking metadata, expose it for catalog and arbitrary installed chat models, persist the selected per-model value using existing `ollama_think`, pass supported values through native chat calls, and render dynamic settings/quick-picker controls. Preserve boolean-only Thinking and Qwen3 compatibility. Treat direct Hugging Face inference as out of scope because LocalGPT currently has no HF chat provider; HF models surfaced through Ollama use the same discovery path only when Ollama advertises metadata.
- Acceptance: named-level and bool-only fixtures produce exact model-specific options/default; unknown/invalid metadata does not show guessed controls or send an unsupported override; custom installed Ollama models show their controls in Settings and quick picker; saving is per-profile/per-model; runtime receives exact supported string/boolean; existing Qwen3 hybrid OFF, reasoning display/privacy, token budgets, and legacy `auto/on/off` remain intact. No live inference, model pull, DB/profile mutation, or server restart during implementation.
- Stages: R1 provider metadata parsing/API exposure + tests (complete; 35 targeted tests, py_compile, and `git diff --check` passed); R2 settings persistence/runtime serialization + compatibility tests; R3 Settings and quick-picker UI + UI regressions; R4 affected provider/architecture/testing/changelog docs and final validation.
- Baseline: branch `feature/prompt-rag-security-hardening`, clean working tree. Relevant existing code uses model-name heuristics in `web_ui/js/app.js`, stores `ollama_think` as a text value, and currently serializes native thinking as boolean only. Direct HF chat provider is absent. Existing active progress file is retained per repository `AGENTS.md`; no second progress file is created.
- Deferred: direct HF inference/provider installation and reasoning metadata adapters for non-Ollama runtimes.
- R1 implementation: `app/services/models.py` queries the configured native Ollama `/api/show` endpoint, preserves CLI fallback, sanitizes `{values, default}` metadata, and exposes it on installed/custom and catalog model records. Explicit `[false]` stays distinct from absent metadata. Added `tests/test_ollama_thinking_metadata.py` and kept existing CLI fallback tests offline in `tests/test_chat_vision_runtime.py`.
- R1 validation: `venv/bin/python -m unittest tests.test_ollama_thinking_metadata tests.test_model_install_state tests.test_chat_vision_runtime tests.test_ollama_pull -v` — 35 passed; targeted `py_compile` and `git diff --check` passed. No live inference/pull, profile or DB mutation, or restart.
- R2 implementation: shared resolver/validator in `app/services/thinking.py`; strict bool/string settings input; booleans persist canonically as legacy `on/off`, while model-declared named values persist verbatim. Chat budgets treat named levels as thinking-enabled; native sync/stream payloads preserve exact bool/string values and validate named values against `/api/show`. Qwen3 hybrid boolean OFF retains `/no_think`; ASR pipeline continues to accept legacy settings.
- R2 validation: 113 focused tests passed across settings, metadata, router, Vision, and continuation; targeted `py_compile` and `git diff --check` passed. A broader 185-test regression had only the two previously documented ASR pipeline failures. No live inference/pull/restart or profile mutation.
- R3 implementation: `web_ui/js/model_thinking.mjs` interprets model-declared metadata; Settings, desktop/mobile header menu, and quick model picker now expose per-model values, including custom installed models. Named values remain verbatim, boolean models keep ON/OFF compatibility, Auto uses Ollama default, unsupported/unknown models have no invented control, and reasoning trace visibility remains separate.
- R3 validation: full frontend Node suite `node --test tests/*.test.mjs` — 50 passed; `node --check web_ui/js/app.js` and `git diff --check` passed. No live backend/browser visual QA; user-facing runtime testing remains for after implementation.
- R4 documentation updated: `docs/knowledge/providers.md`, `docs/knowledge/ui.md`, `docs/knowledge/backend.md`, `docs/ARCHITECTURE.md`, `docs/TESTING.md`, `docs/CHANGELOG.md`, and `docs/BACKLOG.md` now describe per-model Ollama metadata, exact named levels, unsupported/unknown behavior, and the direct-HF limitation.
- R4 validation: `venv/bin/python -m unittest tests.test_ollama_thinking_settings tests.test_ollama_thinking_metadata tests.test_model_router tests.test_chat_vision_runtime tests.test_chat_continuation -q` — 113 passed; `node --test tests/*.test.mjs` — 50 passed; `node --check web_ui/js/app.js`, targeted `py_compile`, and `git diff --check` passed. Non-fatal existing datetime deprecation/resource warnings and mocked Metal fallback logs appeared. No live Ollama inference, browser visual QA, model download, profile mutation, or LocalGPT restart; user-facing acceptance remains pending.
- R4 checkpoint: permanent documentation and this progress update are checkpointed separately from the three implementation commits. The larger multimodal plan remains active, so retain this single progress record.

### MODEL-INVENTORY-DEDUP — display Ollama tags instead of digest IDs

- Status: `completed`; screenshot showed configured Ollama models duplicated as `installed_custom` entries named by 12-character digests.
- Root cause: `buildSelectableChatModels()` preferred inventory `id` over `name`, but Ollama uses `id` for the content digest and `name` for the actual selectable model tag. This caused both failed catalog deduplication and digest labels.
- Scope: prefer runtime `name` when present, retain `id` fallback for catalog-like records, and add regression coverage for mixed inventory/catalog records. Do not change Ollama model inventory or delete models.
- Acceptance: configured installed models appear only once with catalog labels; a genuinely custom installed model uses its Ollama tag, never the digest; existing embedding-only filtering remains intact.
- Validation: `node --test tests/chat_model_catalog.test.mjs` — 2/2; `node --test tests/*.test.mjs` — 50/50; `node --check web_ui/js/app.js` and `git diff --check` passed. No browser/server changes or Ollama mutation; user should refresh the UI to verify presentation.
- Checkpoint: this UI inventory correction is committed separately; larger multimodal plan remains active.

### LLM-LIBRARY-UX — separate model choice from secondary actions

- Status: `completed`; replaced the visually crowded model-card grid with grouped, compact rows.
- Scope delivered: installed and available models are separated into counted sections; each row presents concise status/meta and one primary action; update/delete/details are behind a keyboard-accessible “Действия” disclosure. Model selection, install/update/delete flows, detail tooltip, utility-model behavior, catalog data, and other model libraries remain unchanged.
- Acceptance: grouping and one-primary-action structure have regression coverage; secondary actions are discoverable without competing in every row; keyboard focus, touch sizing, and dark/light styles are supported. Manual visual acceptance remains pending user refresh/inspection of the running UI.
- Validation: `node --test tests/chat_reasoning_ui.test.mjs` (9/9), `node --test tests/*.test.mjs` (51/51), `node --check web_ui/js/app.js`, `node tests/markdown_rendering.test.mjs` (4/4), and `git diff --check` all pass.
- Checkpoint: ready for a focused commit; no backend restart or model download is needed because this is a static UI change.

### Explicitly unchanged / deferred

- ASR accuracy on the user's 5:59.8 MP3 remains an optional manual reference-transcript exercise; short public-set smoke is not a substitute.
- User considers current Vision/OCR capabilities sufficient; real photographed-table and degraded-image acceptance remains deferred.
- Optional actual model-bundle transfer to another device remains deferred until a second device is available.
- GigaAM, agent modes and image generation remain deferred.

## Known limitations

The public ASR sample is only 9 short studio-recorded scripted utterances; it does not assess noisy/overlapping speech, diarization, long-form drift or the user's specific vocabulary. Synthetic Vision/OCR fixtures do not establish real camera-photo accuracy. Tesseract flatten-text CER does not measure cell/row association; the tested sparse-text mode still omitted quantity values. Vision still confuses visually similar Latin/Cyrillic glyphs and status wording; do not normalize these automatically. Numeric temperature and peak per-process memory remain unavailable. Lexical RAG trace remains a review signal, not semantic proof. Image generation is deferred.
