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

1. **ASR live input-quality checks (in progress):** short, silent/no-speech, noisy and abruptly ending recordings; compare against reference text when available. Keep processing sequential and report coverage, false phrases, end-of-file behavior and model/runtime.
2. **Chat/RAG model comparison:** finish coverage of installed models, especially incomplete memory capture, and distinguish retrieval/context delivery from a model ignoring supplied evidence. Do not download models.
3. **Vision/OCR quality:** test screenshots, tables and small text; record actual model provenance and OCR mode.
4. **Mac resource control:** measure memory/residency and temperature where observable; verify unload and sequential execution.
5. **Optional user acceptance:** perform a real model-bundle transfer to another device if one is available. Automated relocation tests are already complete.

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

## Source records

- [Architecture](ARCHITECTURE.md)
- [Testing](TESTING.md)
- [Changelog](CHANGELOG.md)
