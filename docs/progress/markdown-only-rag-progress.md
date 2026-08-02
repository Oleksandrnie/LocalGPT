# Markdown-only RAG Progress

## Task

- Goal: make Markdown the sole RAG source format and remove automatic MD→JSON duplication from ingestion.
- Problem: every Markdown source currently creates and indexes a JSON companion that receives higher retrieval priority, duplicating content and consuming the limited RAG context.
- Expected result: uploads, scanning and retrieval use `.md` only; existing JSON runtime files are left untouched but no longer indexed; the UI and documentation state this clearly.
- Source specification: user request of 2026-08-03.
- Branch: `codex/rag-source-ingestion`.
- Started: 2026-08-03.
- Current status: in progress.
- Current stage: Stage 3 — UI and documentation cleanup.

## Instructions and precedence

- Direct user requirements: create a new branch; inspect existing database and Q&A; make Markdown the only RAG format because MD+JSON duplication harms context and answer quality.
- Applicable AGENTS.md rules: preserve unrelated changes; use feature boundary; create/update progress; validate each stage; checkpoint commits are required by repository workflow.
- Git authorization: branch creation explicitly authorized; focused stage commits required by repository instructions.

## Scope lock

### In scope

- `backend/apps/rag/` ingestion, supported-file contract and retrieval context.
- RAG UI upload filter/status wording.
- RAG tests and affected RAG documentation.

### Out of scope

- Changing user-owned files in `rag_sources/` or deleting existing JSON files.
- Replacing the current local-hash embedding algorithm.
- Changing chat-model behaviour beyond RAG context contents.

### Risks and rollback concerns

- Existing manual JSON sources will stop being indexed; this is intentional per user request, while files remain on disk for recovery.
- Reindex must remove their existing database records without deleting user files.

## Baseline

- Current behavior: `.txt`, `.md`, and `.json` are accepted. Ingest creates JSON for every MD, indexes both, and marks JSON as the source of truth.
- Runtime database: active Default profile has RAG enabled and 12 manual-file documents: six MD files and six auto-generated JSON companions.
- Unrelated user changes to preserve: deletion of `rag_sources/profile_2_third_party/third_party.templates.json` was present before this task.

## Architecture

- Current flow: UI upload → `save_uploaded_files()` → auto-JSON generation → scan/index each supported file → top-k chunks → chat system context.
- Target flow: UI upload → Markdown-only validation → scan/index Markdown files → top-k chunks → chat system context.
- Data and ownership: RAG stays profile-scoped. Existing user files are not removed; stale SQLite documents are reconciled on ingest.

## Implementation stages

### Stage 1 — Investigate and define contract

- Goal: verify the live data and current RAG flow, then specify regression tests.
- Status: completed
- Validation: inspect source, SQLite state, existing RAG tests and chat preparation.
- Completion criterion: confirmed cause and precise Markdown-only contract. Completed.
- Proposed checkpoint commit: none (research only).

### Stage 2 — Markdown-only ingestion

- Goal: remove JSON/TXT acceptance and auto structuring; ensure reindex drops legacy index records without deleting files.
- Status: completed
- Validation: targeted RAG tests covering Markdown prompt context, legacy JSON index cleanup, deletion and profile isolation.
- Proposed checkpoint commit: `Make RAG ingestion Markdown-only`.

### Stage 3 — UI and documentation cleanup

- Goal: update upload affordances and user documentation to reflect one source per document.
- Status: pending
- Validation: static UI check, targeted tests and diff review.
- Proposed checkpoint commit: `Document Markdown-only RAG sources`.

### Stage 4 — Final validation and cleanup

- Goal: run proportional suite, record permanent documentation and remove this progress file.
- Status: pending
- Proposed checkpoint commit: `Complete Markdown-only RAG cleanup`.

## Decisions

### Markdown is the only indexed source

- Decision: accept and index only `.md`; no generated companion JSON.
- Reason: this removes duplicated chunks and a misleading artificial priority, matching the user's requested operational model.
- Consequences: old JSON remains safely on disk but is excluded after next index; documents will instruct users to migrate any needed JSON facts into Markdown.

## Progress log

### 2026-08-03 — baseline

- Completed: created branch and inspected RAG source, chat integration and the live SQLite index.
- Also inspected the live chat history: one 12-message greeting-only session; no RAG query exists there.
- Stage 2 completed: `.md` is the sole accepted suffix; auto-JSON generation and JSON truth priority were removed; legacy JSON index records are reconciled without deleting user files.
- Validation: four targeted `LocalGPTPipelineMemoryTestCase` tests passed.
- Next action: finish UI and documentation validation.

## Validation results

- Inspection: completed; no commands that modify runtime data were run.
- Remaining uncertainty: need test coverage for filtering legacy JSON records during the next ingest.

## Continuation state

- Current stage: Stage 3.
- Current repository state: branch `codex/rag-source-ingestion`; one unrelated deleted runtime JSON file remains unstaged.
- Next exact action: run full proportional validation and inspect the complete diff.
