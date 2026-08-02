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

- Status: completed.
- Confirmed GGML/CoreML are present but `models/whisper_cpp/bin/whisper-cli` is absent. Chat dictation now blocks before microphone recording, opens Settings → ASR → Library, and directs the user to «Дособрать»/«Загрузить».
- Validation: focused UI contract test, JavaScript syntax check and whisper.cpp model-status test pass.
- Checkpoint: `Guide dictation setup before recording`.

## Validation

- Planned: targeted RAG unit tests, direct search assertion, compile/static checks.
- Known unrelated failure: full `test_pipeline_memory` has three pre-existing ASR pipeline failures recorded in `docs/BACKLOG.md`.

## Continuation state

- Next action: run final proportional validation, inspect the complete diff, then delete this progress file in cleanup.
