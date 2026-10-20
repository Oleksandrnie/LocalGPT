# Multimodal audit and quality plan

Permanent plan for the staged improvement of LocalGPT chat, RAG, memory, ASR, Vision/OCR and resource usage. This document records the approved program, completed outcomes and next stages; execution state is maintained separately under the repository workflow.

## Execution protocol

Stages are executed sequentially on the Mac. For this program, GPT-6 Luna with xHigh effort handles reasoning, evidence synthesis and test-result analysis; GPT-6.1 Sol with Medium effort makes architecture and technical-design decisions. The implementation model is selected for each stage according to the user's task-specific instructions. Astra review is never automatic: use Astra only after the user's explicit approval; GPT-6.1 Sol High may substitute for Astra only with that approval. Each stage has its own scope, validation and checkpoint; do not start parallel local model inference or download models without approval.

Work is sequential on the Mac: no parallel local model inference, unnecessary model downloads or unbounded resident runtimes. The active repository is `/Users/oleksandr/Documents/Custom files/1. Github Repositories/LocalGPT`.

## Model allocation

| Responsibility | Model and effort |
| --- | --- |
| Reasoning, synthesis of evidence, interpretation of test results and work sequencing | GPT-6 Luna, xHigh |
| Architecture decisions and technical design | GPT-6.1 Sol, Medium |
| Implementation | Set per stage from the user's explicit task instruction; do not infer it from the analysis model |
| Independent Astra review | Only with explicit user approval; GPT-6.1 Sol High may substitute only with approval |

These are Codex work roles, not LocalGPT runtime-model settings. Reasoning effort does not justify running multiple local inference jobs at once.

## Remaining work — approved order

1. **Remaining Vision/OCR coverage:** supplied screenshots/small text and a synthetic clean-table baseline are complete. Real-world/complex table handling and Russian OCR assistance remain open pending a representative user table image and Russian Tesseract traineddata; do not download language data without approval.
2. **Optional user acceptance:** perform a real model-bundle transfer to another device if one is available. Automated relocation tests are already complete.

## Deferred

- GigaAM feasibility/provider integration; retain the current Whisper path for now.
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

Tesseract 5.5.3 is installed, but its available traineddata is only `eng`, `osd`, and `snum` (no Russian). A local `eng`-only pass on the mixed-language small-text screenshot returned no text. Therefore Russian Tesseract OCR and OCR-assisted modes were not validated; do not install language data without approval. No Vision model remained loaded after each test. The 7B run reached about 7.2 GB resident and free memory recovered to about 81% afterward; the 3B run reached about 4.6 GB and recovered to about 77%. macOS reported no thermal/performance warning; numeric temperature and peak-process RSS remain unmeasured.

The Vision/OCR spot-check stage is complete for the supplied screenshots, small text and synthetic clean-table baseline. Real-world/complex table handling and Russian OCR assistance remain open. Keep settings unchanged; do not download models or language data without approval.

## Mac resource control — bounded live lifecycle smoke completed

On 2026-10-20, with no Ollama model resident and system-wide free memory at about 79%, ran sequential, short local generation checks on already-installed models. `qwen2.5:3b-instruct` returned `ГОТОВО`; Ollama reported about 2.2 GB resident and free memory fell to 66%. An explicit `keep_alive=0` unload cleared `ollama ps` and memory recovered to 78%. Then `qwen3:4b` reached about 3.2 GB resident and free memory fell to 59%. Its 12-token and 64-token probes used the budget in the thinking field and returned no final response; count this only as a load/residency check, not an answer-quality result. Explicit unload again cleared `ollama ps`; free memory recovered to 75%. No models overlapped.

`pmset -g therm` reported no thermal or performance warning before, during or after the checks. macOS did not expose a numeric temperature, and `ollama ps`/`top` snapshots are not peak per-process RSS measurements. Swap use was about 4.02 GB at baseline and 3.98 GB after the tests; this is a system snapshot, not proof of model-caused swap behavior. Earlier 4B/12B comparison remains relevant: Mistral Nemo 12B reached about 12 GB resident and free memory fell to 6%, then recovered after unload. These observations support sequential loading and explicit unload for the tested cases, but do not establish a universal memory ceiling or thermally safe sustained workload.

The Vision 7B table run reached about 7.3 GB resident while system-wide free memory fell to 17%; after completion and explicit unload, free memory recovered to 72% and `ollama ps` was empty. Resource lifecycle smoke is complete for observable measurements. Detailed temperature and peak-process-RSS instrumentation remain unavailable in this environment; no repository/model settings changed and no model was downloaded.

## Source records

- [Architecture](ARCHITECTURE.md)
- [Testing](TESTING.md)
- [Changelog](CHANGELOG.md)
