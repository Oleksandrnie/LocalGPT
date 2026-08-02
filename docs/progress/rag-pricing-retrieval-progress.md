# RAG Pricing Retrieval Progress

## Task

- Goal: ensure pricing queries retrieve the indexed Markdown pricing source before generic profile/template chunks.
- Problem: `third_party.kb.pricing.md` is indexed, but the query «какие цены есть на услуги» does not trigger the pricing boost because it only checks the singular stem `цена`.
- Expected result: common price/service wording selects pricing chunks within top-k and supplies them to chat.
- Source specification: user bug report and screenshot, 2026-08-03.
- Branch: `codex/rag-source-ingestion`.
- Current status: in progress.
- Current stage: implementation.

## Scope lock

- In scope: pricing intent detection in `backend/apps/rag/service.py`, targeted regression test, and diagnosis/fix for the ASR whisper.cpp availability error shown in the screenshot.
- Runtime evidence: `third_party.kb.pricing.md` is indexed. Search for «какие цены есть на услуги» ranks its first chunk sixth; generic chunks consume the top five.

## Stages

### Stage 1 — RAG pricing retrieval

- Status: completed.
- Added pricing word stems (including `цен`) and applied the pricing boost before the non-positive hash-score guard.
- Validation: targeted tests pass; the live SQLite index now ranks `third_party.kb.pricing.md` chunks 1–4 for «какие цены есть на услуги».
- Checkpoint: `Prioritize pricing Markdown for price queries`.

### Stage 2 — ASR whisper.cpp availability

- Status: pending.
- Inspect configured binary path, installed artifacts and the ASR provider's error path; implement a scoped correction only if the repository/runtime setup is at fault.
- Checkpoint: `Fix whisper.cpp availability detection` (only if a tracked fix is warranted).

## Validation

- Planned: targeted RAG unit tests, direct search assertion, compile/static checks.
- Known unrelated failure: full `test_pipeline_memory` has three pre-existing ASR pipeline failures recorded in `docs/BACKLOG.md`.

## Continuation state

- Next action: patch pricing intent markers and prove `third_party.kb.pricing.md` is retrieved for the reported query.
- Next action: inspect whisper.cpp configuration and installed artifacts for Stage 2.
