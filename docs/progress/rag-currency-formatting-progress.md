# RAG Currency Formatting Progress

## Task

- Goal: standardize currency notation in the active RAG sources and commercial-offer output.
- Expected result: rubles use `₽` after a space; US dollars and euros use `$`/`€` before the value; no accidental currency glyphs reach replies.
- Source specification: user task of 2026-08-03.
- Branch: `dev`.
- Current status: in progress.
- Current stage: Stage 1.

## Instructions and precedence

- Direct requirements: audit all RAG files, correct monetary notation, record ruble/dollar/euro rules, and verify commercial-offer/calculation output.
- Applicable rules: repository `AGENTS.md`; project-progress-workflow skill.
- Git authorization: repository workflow requires focused stage commits; no separate branch requested.

## Scope lock

### In scope

- Active Markdown sources under `rag_sources/profile_1_Default/`.
- RAG authoring guidance in `rag_sources/README.md` and RAG knowledge documentation.
- Chat response formatting guardrail, sanitizer, and focused unit tests.

### Out of scope

- Changing tariff amounts or commercial terms.
- Editing unrelated runtime transcripts or generated task deltas.

### Risks and decisions

- The active SEO Business price is `75 000 ₽` per month in RAG; preserve it because the task only authorizes formatting changes.
- Normalize the observed `⽇` only when it follows a number, avoiding changes to unrelated text.

## Baseline

- Working tree: clean on `dev`.
- RAG has ruble examples but no complete dollar/euro rule; templates use `руб.`.
- Chat prompt only specifies Russian grouping; sanitizer does not handle `⽇`.
- Relevant test: `tests.test_pipeline_memory` covers global response formatting and reply sanitization.

## Implementation stages

### Stage 1 — RAG source rules and templates

- Goal: make every commercial/pricing source use one explicit currency contract.
- Status: completed
- Validation: targeted repository-wide scans of active RAG Markdown for old `руб.` and `⽇`; review examples.
- Proposed checkpoint commit: `docs(rag): standardize currency formatting guidance`.

### Stage 2 — Chat output enforcement

- Goal: give generated answers the same contract and normalize the observed erroneous glyph.
- Status: in_progress
- Validation: focused `tests.test_pipeline_memory` tests.
- Proposed checkpoint commit: `fix(chat): enforce currency display format`.

### Stage 3 — Verification and cleanup

- Goal: run proportional validation, update permanent RAG documentation, and remove this temporary record.
- Status: pending
- Validation: `git diff --check`, focused unit tests, compile baseline, and RAG scans.
- Proposed checkpoint commit: `docs(rag): record verified currency formatting`.

## Progress log

### 2026-08-03 — baseline

- Completed: read repository/RAG/testing guidance and inspected every active RAG Markdown file.
- Findings: `third_party.kb.pricing.md` contains consistent `₽`; `third_party.templates.md` contains the legacy `руб.` abbreviation; no active RAG source contains `⽇`.
- Next action: add a shared currency contract and update commercial templates.

### 2026-08-03 — Stage 1 complete

- Changed: `rag_sources/README.md`, the active pricing/index/template Markdown files, and `docs/knowledge/rag.md`.
- Completed: recorded the ₽/$/€ contract; corrected both legacy `руб.` template usages; added a calculation-capable commercial-offer template.
- Validation: inspected all active RAG Markdown files; no malformed currency layout remains outside explanatory prohibitions.
- Next action: validate chat guardrail and accidental-glyph sanitizer, then checkpoint Stage 1.

## Continuation state

- Current stage: Stage 2.
- Next exact action: checkpoint the completed RAG source/documentation stage, then finish chat output validation.

## Final checklist

- [ ] Every acceptance criterion and Definition of Done item is checked.
- [ ] Required validation passed or limitations are explicitly accepted.
- [ ] Only affected permanent documentation and records were updated.
- [ ] No unrelated changes or task-owned temporary artifacts remain.
- [ ] Final diff and working-tree state were inspected.
- [ ] Progress file is ready to be deleted.
