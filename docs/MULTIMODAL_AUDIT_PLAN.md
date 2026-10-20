# Multimodal audit and quality plan

Permanent plan for the staged improvement of LocalGPT chat, RAG, memory, ASR, Vision/OCR and resource usage. The working execution log remains in `docs/progress/multimodal-audit-progress.md`; this document records the approved program, completed outcomes and next stages in the repository documentation.

## Execution protocol

Each stage is handled independently and stops at its review boundary:

1. Astra defines the scope, risks and acceptance criteria.
2. The implementation is delegated to a bounded subagent.
3. The implementer adds code, regression tests and affected documentation only for that stage.
4. Astra reviews the diff and validation results.
5. A stage is accepted only after review approval. A commit is created only after explicit user authorization.

Work is sequential on the Mac: no parallel local model inference, unnecessary model downloads or unbounded resident runtimes. The active repository is `/Users/oleksandr/Documents/Custom files/1. Github Repositories/LocalGPT`.

## Model allocation

- GPT Astra: diagnosis, architecture, acceptance criteria and final review.
- GPT-5.6 Sol with medium reasoning: primary implementation for bounded backend, memory, RAG, ASR and persistence stages.
- GPT-5.6 Sol with high reasoning: escalation only for difficult concurrency, lifecycle, data-integrity or architecture problems that medium reasoning cannot resolve.
- GPT Luna with low/medium reasoning: user-facing questions, task kickoff, simple UI and documentation tasks.

Reasoning effort is selected per stage. It is not a reason to run multiple heavy local inference jobs at once.

## Priorities

1. Chat, RAG, settings, memory and instruction adherence.
2. ASR Studio correctness and sequential processing.
3. Optional GigaAM provider evaluation while retaining Whisper.
4. Vision/OCR routing, provenance and image/table quality.
5. Measured Mac resource limits, model unloading and sequential execution.
6. Agent modes and graphics generation only after the core flows are stable.

## Completed: C1 — completed-turn memory boundary

Status: accepted after independent GPT Astra review. No commit was created until the user later authorized checkpointing.

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

## C2 — Chat/RAG/settings and summary quality (implementation complete; awaiting review)

Implemented for review:

- deterministic cross-domain tests prove retrieved evidence and profile instructions reach the actual completion messages;
- bounded post-answer diagnostics trace only a structured manifest of evidence content spans actually sent to the model, excluding service rules, filenames, diagnostic queries and omitted chunks, and distinguish retrieval `not_found` from found evidence that is not lexically traceable in the answer, without treating the heuristic as semantic proof;
- follow-up query composition, completed-turn history and active-profile settings remain continuous;
- automatic chat summaries use content-addressed completed-turn/settings snapshots, whole-turn truncation metadata and source-aware selection of the current matching snapshot in prompts;
- cross-domain regression fixtures without corpus-specific rules.

Deterministic tests and documentation are complete. Astra review is still required. Live answer-quality checks remain separate from unit-test success and were not run in this stage.

## Later stages

- **S1 — ASR validity and lifecycle:** empty, silent, short, noisy and long Russian recordings; queue, cancellation, progress and persistence.
- **S2 — GigaAM feasibility:** primary-source compatibility research and a switchable provider design, with Whisper retained.
- **V1 — Vision/OCR:** routing parity, actual-model provenance, OCR modes, tables and small text.
- **R1 — Resource control:** measured residency, unload behavior, bounded concurrency and thermal-friendly sequential operation.
- **A1 — Agent modes:** only after core acceptance; roles and subagents must have explicit permissions, handoff and rollback boundaries.

## Source records

- [Working progress record](progress/multimodal-audit-progress.md)
- [Architecture](ARCHITECTURE.md)
- [Testing](TESTING.md)
- [Changelog](CHANGELOG.md)
