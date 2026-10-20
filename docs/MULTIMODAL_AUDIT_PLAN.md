# Multimodal audit and quality plan

Permanent plan for the staged improvement of LocalGPT chat, RAG, memory, ASR, Vision/OCR and resource usage. This document records the approved program, completed outcomes and next stages; execution state is maintained separately under the repository workflow.

## Execution protocol

Stages are executed sequentially on the Mac. Codex model routing and review approval rules are defined canonically in the repository-root [`AGENTS.md`](../AGENTS.md); this plan does not duplicate them. Each stage has its own scope, validation and checkpoint; do not start parallel local model inference or download models without approval.

Work is sequential on the Mac: no parallel local model inference, unnecessary model downloads or unbounded resident runtimes. The active repository is `/Users/oleksandr/Documents/Custom files/1. Github Repositories/LocalGPT`.

## Codex agent instructions

See the repository-root [`AGENTS.md`](../AGENTS.md) for the canonical model-routing and review policy. These Codex work roles are separate from LocalGPT runtime-model settings; reasoning effort does not justify running multiple local inference jobs at once.

## Remaining work — approved order

1. **Broader Chat/RAG evaluation:** the controlled single-question comparison across five installed target Chat models is already complete. Extend—not repeat—that baseline with a cross-domain test set and separate checks for retrieval coverage, evidence passed to the model, answer completeness and appropriate abstention. Run one model at a time, use fresh sessions, and do not download models or add corpus-specific rules.
2. **Mac resource measurements:** the sequential load/unload smoke is complete. Measure available per-model/process and system memory signals during representative sequential inference; inspect built-in thermal-pressure reporting. First establish which peak RSS/thermal metrics are available without installing extra utilities; report unavailable numeric temperature as unavailable.
3. **User-recording ASR reference (optional, domain-specific):** the public benchmark below establishes a reproducible baseline. To score the user's own long MP3, a human must verify a 30–60 second slice against the audio; a model transcript alone is not ground truth. A preliminary transcript can be supplied for correction.
4. **Optional transfer acceptance:** perform a real model-bundle transfer to another device if one is available. Automated relocation tests are already complete.

## Deferred

- GigaAM feasibility/provider integration; retain the current Whisper path for now.
- A real camera-photographed table/receipt, perspective/skew and low-quality OCR acceptance; the user considers current Vision/OCR capabilities sufficient for this stage.
- Agent modes/orchestration and image generation until the core chat/RAG, ASR, Vision and resource checks are accepted.

## Completed: C1 — completed-turn memory boundary

Status: accepted after independent GPT Astra review and checkpointed in `d6b9d28` (`fix(memory): bound history to completed turns`).

Implemented:

- Added one chronological completed `user + assistant` turn selector in `app/db.py`.
- Reused it for both retained short history and automatic summary memory.
- Excluded failed, cancelled, active, streaming, partial and orphan rows from the eligible turn set.
- Ensured the recent-history suffix and summary prefix are disjoint and session-scoped.
- Preserved existing summary prompt, model selection, truncation, deduplication, source IDs, RAG, ASR and UI behavior.
- Added temporary-SQLite regression coverage and a mocked compressor test.
- Updated architecture, backend knowledge, testing and changelog documentation.

Impact:

- Failed or unfinished generations can no longer enter automatic summary memory.
- Invalid rows no longer shift the retained-history boundary.
- The active session cannot inherit turns from another session.
- Summary memory and short history now describe separate completed conversation ranges.

Validation:

- Memory, isolation, RAG and security baseline: 53/53 passed with deterministic `local_hash` settings.
- Summary/settings checks: 2/2 passed.
- Additional temporary-DB boundary probes for invalid statuses, keep values and disjoint coverage passed.
- `git diff --check`, Python compilation, JavaScript syntax and Markdown checks passed.
- No live model inference was needed for this stage.

Known limits deliberately deferred to C2: existing summary cleanup, summary regeneration after `mem_turns` changes, truncation and repeated-summary behavior, and count-based summary source IDs.

## C2 — Chat/RAG/settings and summary quality (completed and checkpointed)

Implemented for review:

- deterministic cross-domain tests prove retrieved evidence and profile instructions reach the actual completion messages;
- bounded post-answer diagnostics trace only a structured manifest of evidence content spans actually sent to the model, excluding service rules, filenames, diagnostic queries and omitted chunks, and distinguish retrieval `not_found` from found evidence that is not lexically traceable in the answer, without treating the heuristic as semantic proof;
- follow-up query composition, completed-turn history and active-profile settings remain continuous;
- automatic chat summaries use content-addressed completed-turn/settings snapshots, whole-turn truncation metadata and source-aware selection of the current matching snapshot in prompts;
- cross-domain regression fixtures without corpus-specific rules.

Deterministic tests and documentation are complete; Astra review approved the implementation and the focused checkpoint is `c83767e` (`feat(chat): trace RAG evidence and snapshot memory`). Live answer-quality checks remain separate from unit-test success and are part of the remaining model-comparison work.

## ASR3 — live ASR input-quality smoke (completed; accuracy score pending reference)

Ran sequentially through the user's already-running LocalGPT backend at `127.0.0.1:8000`, using `large-v3-turbo` with the `whisper_cpp` backend, Russian language, automatic prompt, four runtime threads, and `store_result=false`. No models were downloaded and the original MP3 was not modified. Temporary derived fixtures were removed after the run.

- Existing 5:59.8 Russian MP3 baseline: completed in about 41 seconds with 39 segments spanning 0.00–359.81s. This verifies long-input completion and timestamp coverage, not word-level accuracy.
- 8-second real-audio excerpt: completed with 3 segments spanning 0.07–8.00s.
- 10.5-second abrupt crop: completed with 2 segments spanning 0.07–10.53s; transcript reached the clipped endpoint without a task failure.
- The same crop with synthetic low-level pink noise completed with 2 segments. Its recognized words broadly matched the clean crop; punctuation/segmentation differed. This is a synthetic noise smoke, not a field-noise benchmark.
- 10-second digital silence returned `empty_transcription`; no transcript record was produced.
- Every task result reported `stored=false` and `transcript_id=null`; the ASR task slot returned to idle after each run. No `whisper-cli` process remained after the sequence.

The long recording has no supplied reference transcript, so no WER/CER or claim of transcription accuracy is available. System-wide memory free percentage was 51% before and 53% after; macOS reported no thermal/performance warning, but no numeric temperature or per-process peak-memory measurement was captured. Those measurements remain in the dedicated resource stage.

## Chat/RAG live model comparison — completed for installed target models

Ran the same Russian CMS question sequentially in fresh, disposable sessions in profile `Clients RAG test` (profile 6), with profile RAG enabled and each target model selected explicitly. The installed target chat models tested were `qwen2.5:3b-instruct`, `qwen2.5:7b-instruct`, `qwen3:4b`, `qwen2.5-coder:7b` and `mistral-nemo:12b`. Qwen 2.5 7B also passed a separate completed-turn memory probe by recalling the exact synthetic label `RZ-7314-Q`. The 0.6B model remains the optional Smart Router and was not treated as a target answer model; its prior memory/router result remains listed above. `qwen3:8b` and vision/embedding models were not installed target chat models, and no downloads were made.

All five clean RAG runs received the same five chunks from `rag_third_party.md` and returned a short list containing WordPress and Битрикс. This was consistent across model families, but not complete relative to all CMS mentions in the corpus. A separate direct search with the exact chat query returned `supported` while some selected evidence spans were generic or unrelated to CMS; a semantically similar phrasing produced a `conflict` status and exposed additional CMS mentions. The chat lexical trace marked the two-item answers `evidence_traceable`, which confirms word overlap only—not completeness, entailment or resolution of conflicting source passages. An earlier Qwen 2.5 7B answer from a session that also contained the memory probe differed; it was excluded from the controlled comparison because prior turns were a confounder.

Interpretation: for this deliberately noisy RAG corpus, the recurring short answer is not a model-specific failure. Retrieval/ranking, facet coverage and source ambiguity remain plausible upstream contributors; the current lexical trace cannot prove which factor caused each omission. Do not add CMS-specific rules. Test-fixture sessions were deleted after use. No repository code or profile settings were changed.

Resource observation for the dedicated Mac stage: during sequential testing, `qwen3:4b` reached a reported resident size of about 7.5 GB and system-wide free-memory percentage fell to 18%; `mistral-nemo:12b` reported about 12 GB and free memory fell to 6%. Each model was unloaded after its test; free-memory percentage recovered to about 64–80%. macOS reported no thermal warning, but numeric temperature and peak per-process memory remain unmeasured. The 12B test was allowed to return its answer, then explicitly unloaded; no concurrent inference ran.

## Vision/OCR quality — live smoke completed; table/OCR-language coverage remains open

On 2026-10-20, used two existing image attachments from the Personal profile's prior “выпиши текст” chat in fresh temporary sessions; did not change profile settings or download models. With OCR assist Off and image-RAG not requested, the 7B Vision run (`qwen2.5vl:7b`) returned the screenshot's visible Russian response text nearly verbatim. The initial route plan named `vision_context` with text fallback `qwen2.5:3b-instruct`, but the task result's actual completion model was `qwen2.5vl:7b`; code inspection confirms non-RAG image prompts switch to direct Vision completion. Use the task result's `model` as actual provenance, not the initial route-plan label.

A separate direct `qwen2.5vl:3b` run transcribed the small mixed Russian/English Vision-settings screenshot exactly, including the selected `Off` and the second `Off` option. Both screenshot runs had `image_rag_included=false`; the 7B run's RAG diagnostics were `disabled`.

To add a controlled table baseline without using private/user data, generated a temporary synthetic 4-column × 3-row image with unique mixed Cyrillic/Latin values. Both direct `qwen2.5vl:3b` and `qwen2.5vl:7b` returned all 12 data cells exactly in the requested JSON shape; `image_rag_included=false` and OCR evidence remained empty. The generated image and temporary test sessions were removed. This validates a clean, high-contrast table only—not dense, skewed, low-resolution, merged-cell or real-world documents. There was no independent expected-transcript file for automated character-level scoring on the screenshots.

On 2026-10-20, extended that baseline with a generated, visually checked 2040×1070 high-contrast inventory table containing 8 rows × 9 body columns (72 cells), a two-level/grouped header, mixed Latin/Cyrillic look-alike identifiers, arrows, decimal commas, thousands separators, quotes and notes. The identical image and extraction prompt were run sequentially through the current LocalGPT app in fresh Personal-profile sessions (id 4): first `qwen2.5vl:3b`, then `qwen2.5vl:7b`. Both actual task results identify the selected Vision model as the direct responder. OCR assist was Off, image RAG was not requested, effective RAG was false, and no OCR evidence was supplied. The existing profile temperature (0.25) and 512-token output cap were preserved; no settings were changed.

- The 3B result contained all 72 body cells; 68/72 cell strings matched the synthetic source exactly. Four cells differed only in visually confusable Latin/Cyrillic glyphs (`K/К`, `C/С`, `A/А`, `T/Т`). Numeric values, remaining text and row/column associations matched. The model returned the subheaders but omitted the three grouped-header labels.
- The 7B result emitted 69/72 body cells and stopped mid-final row, omitting its price, status and note; the configured output cap was 512 tokens. Four emitted cell strings had the same class of Latin/Cyrillic confusions, leaving 65/72 expected cells exactly represented. It included the group labels but formatted them as a ragged Markdown header rather than a consistent merged-header structure. The task state was still `completed`, so a successful task state does not imply a complete table extraction. Because the task result exposed neither generated-token count nor provider stop reason, the cap is a plausible but unconfirmed cause of truncation.

Resource/lifecycle observations: the 3B run reported about 4.6 GB resident; the 7B run about 7.2 GB, with system-wide free memory at 12–13%. After explicit unload, `ollama ps` was empty and free memory recovered to 70%; macOS reported no thermal/performance warning. Temporary sessions and the generated fixture were deleted. Numeric temperature and peak per-process RSS remain unavailable. This was a controlled synthetic stress test, not a real photo/table benchmark; blur, skew, perspective, low resolution, noise and Russian OCR assistance remain unvalidated.

At the initial screenshot smoke, Tesseract had only `eng`, `osd`, and `snum`; English-only OCR returned no text on the mixed-language screenshot. The follow-up below installed Russian traineddata for a controlled evaluation. No profile setting changed. The screenshot-smoke resource observations remain: 7B reached about 7.2 GB resident and free memory recovered to about 81%; 3B reached about 4.6 GB and recovered to about 77%. macOS reported no thermal/performance warning; numeric temperature and peak-process RSS remain unmeasured.

The initial synthetic table tests exposed mixed-script glyph ambiguity and a dense-table response-cap problem; both were measured in the follow-up stages below. A genuine photographed business table remains optional user acceptance. Do not automatically substitute Latin/Cyrillic look-alikes or change profile defaults based on these synthetic fixtures.

**Status correction:** The two preceding paragraphs describe the earlier baseline only. The follow-up has since installed and evaluated Russian Tesseract data, tested a photo-like synthetic table, and implemented explicit Vision output-budget/truncation handling; the current measurements and scope are below.

## Vision V4 — per-request output limit and truncation handling

The direct provider baseline confirmed the cause of dense-table truncation: on the 72-cell clean table, `qwen2.5vl:7b` with `num_predict=512` ended with `done_reason=length` at exactly 512 generated tokens. At 1024 it returned valid JSON, all 72 cells, `done_reason=stop`, and 551 generated tokens. A 2048 cap produced the same answer and token count, so 1024 was sufficient for this fixture; a larger cap did not improve its exact-cell score (66/72). The test was repeated on an 800×280 downscaled, slightly rotated/blurred/JPEG-compressed version: 7B returned all 72 cells at 1024 tokens, stopped normally after 397 tokens, and matched 66/72 cell strings exactly. Remaining errors were four `Оплачен`/`Оплачено` status substitutions and two Latin `A`/Cyrillic `А` substitutions in `Склад A`.

Implemented profile setting `vision_output_tokens`, wired through Vision inference only. Its initial implementation used `0` to inherit the ordinary output budget; the subsequent user-requested default is now 1024, and legacy stored/API `0` resolves to 1024 without requiring a SQLite migration. Explicit values 128–8192 remain supported. UI display/save/reset use 1024 and recommend not going lower because text/table output can truncate; larger tables may require more. Ordinary text responses and their budgets are unchanged. Provider result and streaming-event metadata retain `done_reason` and `eval_count`; length-truncated direct Vision answers and derived Vision context fail instead of persisting as complete. Initial automated coverage: 52 focused backend tests plus 6 attachment/settings UI tests passed; Python compileall passed. The earlier live smoke observed Personal stored at `0`; that historical value now resolves to 1024, with no persistent profile edit required. A complete image-chat submission through the browser remains optional user acceptance; the default increase is not a guarantee of exact transcription.

## Vision V5 / OCR V6 — synthetic table robustness and Russian Tesseract

The known-answer photo-like fixture is a generated synthetic table, not a camera photograph. It shows that a larger response budget prevents truncation but does not fix visual or character ambiguity. A separate 42-cell comparison found 3B returned 42/42 cells on a clean image (with mixed-script glyph errors), while 7B returned 42/42 on a photo-like version; both outputs fit below 512 tokens. Thus completeness and exact transcription are separate measures.

Installed only the official Tesseract [`rus.traineddata`](https://github.com/tesseract-ocr/tessdata_fast/blob/main/rus.traineddata) locally for this evaluation (about 3.7 MB; not a repository asset). The installed language list now includes `rus`. No app profile/default or installed model was changed. On the 72-cell dense fixture, CER is computed over normalized whole-table text (lowercase, `ё→е`, punctuation/spacing removed; expected text 482 characters):

| Fixture | Tesseract language / PSM | CER | Observation |
| --- | --- | ---: | --- |
| Clean | `rus`, 6 | 91.7% (442/482) | Default line-block mode recognized little of the grid. |
| Clean | `rus+eng`, 6 | 91.7% (442/482) | Same poor result. |
| Clean | `rus`, 11 | 8.7% (42/482) | Much more text; row/column association is not retained and quantity cells were omitted. |
| Clean | `rus+eng`, 11 | 5.8% (28/482) | Best clean flattened-text score; still omitted quantity values and confused look-alike scripts. |
| Photo-like | `rus`, 6 / 11 | 55.2% / 41.3% | Significant cell/text loss even with sparse-text mode. |
| Photo-like | `rus+eng`, 6 / 11 | 56.6% / 42.3% | Similar degradation; column and row structure breaks down. |

The current `/ocr/extract` route uses PSM 6 plus auto-crop; on these dense fixtures it returned only title/header fragments for the clean table and partial, misordered fragments for the photo-like table. OCR can be optional evidence to Vision, not a source of guaranteed table structure. Do not change the default PSM or make OCR mandatory based on this synthetic sample.

## ASR V4 — reference-scored Russian short-speech sample

Used nine existing WAVs from the held-out `test` split of [Langswap Dialogs](https://huggingface.co/datasets/langswap/dialogs-ru-emotional-conversations), a scripted, studio-quality expressive Russian dialogue corpus, not spontaneous phone calls. The selected utterances were `part1_{53,71,87,101,103,122,165,166,347}`; one initially selected file was absent from the repository and was replaced with another test-split utterance. Only these selected audio files were downloaded to a temporary directory; the whole corpus was not fetched. Sent sequential requests through the already-running LocalGPT `/transcribe` endpoint using installed `large-v3-turbo` / `whisper_cpp`, forced `language=ru`, automatic prompt, and `store_result=false`; no transcript history rows or model downloads were created.

Across 9 clips (about 91 seconds; 172 reference words; 909 normalized characters), aggregate normalized WER was **2.3% (4/172 word edits)** and CER **0.7% (6/909 character edits)**. Normalization lowercases, treats `ё` as `е`, and removes punctuation/spacing. This is a small public-corpus smoke, not a statistically robust or universally representative score; some errors can reflect reference orthography or expressive delivery, and model-training overlap cannot be excluded. It establishes that the current Whisper path handles these selected short, clean studio clips well, but says nothing about long noisy recordings, overlapping speakers or domain names. For the user's own 5:59.8 MP3, a human-reviewed 30–60 second excerpt is still needed for a domain-specific score; a Whisper/model draft can accelerate proofreading but cannot be its own reference.

## Mac resource control — bounded live lifecycle smoke completed

On 2026-10-20, with no Ollama model resident and system-wide free memory at about 79%, ran sequential, short local generation checks on already-installed models. `qwen2.5:3b-instruct` returned `ГОТОВО`; Ollama reported about 2.2 GB resident and free memory fell to 66%. An explicit `keep_alive=0` unload cleared `ollama ps` and memory recovered to 78%. Then `qwen3:4b` reached about 3.2 GB resident and free memory fell to 59%. Its 12-token and 64-token probes used the budget in the thinking field and returned no final response; count this only as a load/residency check, not an answer-quality result. Explicit unload again cleared `ollama ps`; free memory recovered to 75%. No models overlapped.

`pmset -g therm` reported no thermal or performance warning before, during or after the checks. macOS did not expose a numeric temperature, and `ollama ps`/`top` snapshots are not peak per-process RSS measurements. Swap use was about 4.02 GB at baseline and 3.98 GB after the tests; this is a system snapshot, not proof of model-caused swap behavior. Earlier 4B/12B comparison remains relevant: Mistral Nemo 12B reached about 12 GB resident and free memory fell to 6%, then recovered after unload. These observations support sequential loading and explicit unload for the tested cases, but do not establish a universal memory ceiling or thermally safe sustained workload.

The Vision 7B table run reached about 7.3 GB resident while system-wide free memory fell to 17%; after completion and explicit unload, free memory recovered to 72% and `ollama ps` was empty. Resource lifecycle smoke is complete for observable measurements. Detailed temperature and peak-process-RSS instrumentation remain unavailable in this environment; no repository/model settings changed and no model was downloaded.

## Source records

- [Architecture](ARCHITECTURE.md)
- [Testing](TESTING.md)
- [Changelog](CHANGELOG.md)
