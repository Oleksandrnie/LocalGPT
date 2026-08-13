# Prompt RAG Security Hardening Progress

## Task

- Goal: выполнить доказательный аудит и поэтапно усилить RAG grounding, prompt composition и LLM/runtime security boundaries LocalGPT.
- Expected result: выполнить acceptance criteria из `docs/PROMPT_RAG_SECURITY_AUDIT_SPEC.md` без клиентских данных, скрытых prompt values, secrets и неконтролируемой model/hardware нагрузки.
- Source specification: `docs/PROMPT_RAG_SECURITY_AUDIT_SPEC.md` (рабочая копия побайтно совпадает с переданным пользователем внешним файлом).
- Base branch: `dev` at `c32a101c876757890bacd4d3c89022e88f97e8e3`, verified equal to `origin/dev` (`0 0`).
- Branch: `feature/prompt-rag-security-hardening`.
- Started: 2026-08-13 16:10 +0300.
- Current status: in_progress.
- Current stage: Stage 2 — Source boundaries and prompt policy (ready for checkpoint).

## Instructions and precedence

- Direct user requirements: apply the named `project-progress-workflow` skill to the supplied specification.
- Task-specific requirements: five staged checkpoints, remediation matrix before Stage 2, no production policy changes in Stage 1 except safe testability/diagnostics, no client data/secrets, proportional QA and final cleanup.
- Applicable repository rules: root `AGENTS.md`; read `docs/README.md`, `docs/ARCHITECTURE.md`, affected knowledge docs and `docs/TESTING.md`; preserve unrelated/user changes; avoid live heavy models unless intentional.
- Conflicts and resolutions: repository normally forbids branch creation without explicit approval, but the task specification explicitly requires and names the feature branch, so it is authorized. Existing modified specification is user-owned and preserved; it will not be staged until its task ownership and checkpoint boundary are reviewed.
- Git authorization: the task specification requires one focused commit per completed stage and a final cleanup commit; no push, force-push, history rewrite or additional branch is authorized.

## Scope lock

### In scope

- Actual prompt/data/source/action flow and trust-boundary audit.
- Synthetic grounding and adversarial regression harness.
- Global-policy/profile-persona separation and trust-aware data envelopes.
- Evaluated retrieval/dedup/diversity/coverage improvements and provenance diagnostics.
- Confirmed ownership, resource, rendering and action/sink boundary fixes.
- Affected permanent documentation, rollout/rollback record and proportional QA.

### Out of scope

- Absolute jailbreak-proof claims, public chain-of-thought, cloud security/embedding services, automatic corpus deletion, automatic actions from model/data, or a new external-agent connector.
- Real client corpus, raw prompt/secret telemetry and unbounded live/hardware tests.
- Unrelated defects or architectural migrations not needed by the specification.

### Affected areas and expected files

- `app/prompts/system_base.md`, `app/roles.py`, chat/RAG services and repositories under `backend/apps/` and `app/` where verified.
- Synthetic fixtures and tests under `tests/`.
- `web_ui/` only for a confirmed security/diagnostic or error-state requirement.
- `docs/ARCHITECTURE.md`, `docs/TESTING.md`, affected `docs/knowledge/*.md`, `docs/CHANGELOG.md`, and `docs/BACKLOG.md` only where facts change or residual work remains.

### Dependencies and compatibility

- Preserve profile isolation, existing profile prompts/persona behavior, persisted task lifecycle, explicit model loading, offline operation and local-hash-v1 compatibility until an eval justifies change.
- Preserve `app/prompts/system_base.md` as runtime data loaded by `app/roles.py`.

### Risks and rollback concerns

- Prompt ordering or migration can silently change existing persona behavior.
- Retrieval changes can improve one golden case while regressing exact facts, latency or memory.
- Over-broad sanitization can remove useful source content; heuristics remain diagnostics, not absolute protection.
- Rollback must restore previous prompt/retrieval behavior without losing user profile prompts or corpus data.

## Baseline

- Current behavior: Stage 1 mapped the prompt/data/action flow and established the synthetic baseline; Stage 2 now separates global policy, profile configuration and all untrusted prompt data. Retrieval quality, claim-level evidence diagnostics and runtime/API controls remain unchanged until their stages.
- Existing tests: repository `unittest` suite plus targeted chat/RAG/UI tests documented in `docs/TESTING.md`.
- Validation commands: targeted synthetic tests per finding, repository static baseline, full unit suite where safe, bounded UI/live checks only when applicable.
- Pre-existing failures: full baseline ran 248 tests with one failure and two errors, all reproducible before task source changes: `test_full_analysis_skips_cleaner_by_default_and_sanitizes_speakers`, `test_pipeline_tasks_are_normalized_for_transcript_record`, and `test_get_plugin_doc_reads_manifest_doc_only`.
- Branch and working-tree state: new feature branch at base commit; modified `docs/PROMPT_RAG_SECURITY_AUDIT_SPEC.md` existed before branch creation.
- Unrelated user changes to preserve: none detected; the modified specification is user-owned and task-related but initially unstaged.

## Architecture

- Current flow: pending code-verified Stage 1 map.
- Target flow: L0 code controls > L1 global policy > L2 profile persona > L3 current request; all RAG/uploads/history/derived text remain L4 data envelopes and model output remains non-executable L5 candidate text.
- Contracts and boundaries: routes validate/serialize; backend-owned services/providers/repositories enforce ownership, budgets and safe sinks; prompts are not the sole security boundary.
- Data and ownership: profile-scoped storage and current authorized sources only; no assistant-history claim counts as evidence without current-source confirmation.

## Implementation stages

### Stage 1 — Evidence-based audit and test harness

- Goal: produce code-backed maps, inventories, threat/remediation registers, grounding baseline and reproducible synthetic tests before production-policy changes.
- Status: completed.
- Actions: inventory entry points/prompts/data/actions/sinks/ownership/limits; build synthetic golden and red-team fixtures; record baseline and remediation matrix.
- Expected result: achieved; every finding has a reproducer or precise code/config evidence and unknown external environments are explicit.
- Validation: targeted audit/grounding/security tests plus safe static baseline.
- Completion criterion: all eight audit deliverables exist in this progress file or task-owned audit artifacts and matrix maps each finding to fix/tests/residual risk.
- Affected files: progress file, synthetic tests/fixtures, minimal safe diagnostics if required.
- Dependencies: none.
- Proposed checkpoint commit: `test(security): add prompt and rag audit baseline`.

### Stage 2 — Source boundaries and prompt policy

- Goal: enforce prompt trust hierarchy while preserving editable profile persona and existing behavior.
- Status: completed; ready for checkpoint.
- Actions: trust-aware prompt builder/data envelopes, compact immutable global guard, profile/default-persona migration, ordering/snapshot and injection tests.
- Expected result: L4 text cannot become instructions; assistant history is not evidence; profile persona remains effective only inside L0/L1 constraints.
- Validation: focused chat/model-router/prompt tests and regression snapshots without secret values.
- Completion criterion: all mapped L4 sources are delimited and tested, migration/rollback rules pass.
- Dependencies: Stage 1 remediation matrix.
- Proposed checkpoint commit: `feat(chat): enforce prompt source boundaries`.

### Stage 3 — RAG retrieval and grounding quality

- Goal: select and implement retrieval/dedup/diversity/coverage changes by reproducible eval.
- Status: pending.
- Actions: compare current local-hash-v1 baseline with lexical/hybrid and optional local semantic candidate; add provenance, coverage/conflict/not_found/inference diagnostics.
- Expected result: CMS + regions and the synthetic golden set meet the recorded threshold without isolation/resource regressions.
- Validation: grounding eval, exact-fact regressions, latency/memory/offline checks and RAG unit tests.
- Completion criterion: selected candidate wins by recorded metrics and golden threshold passes.
- Dependencies: Stage 1 harness and Stage 2 boundaries.
- Proposed checkpoint commit: `feat(rag): improve grounded retrieval and evidence`.

### Stage 4 — Runtime security controls

- Goal: close confirmed Critical/High gaps and proportionally address Medium ownership/resource/rendering/action-sink risks.
- Status: pending.
- Actions: implement code-enforced ownership, redaction, budgets, concurrency/timeout/cancel cleanup and safe output/action boundaries only where findings prove a gap.
- Expected result: failure paths are terminal, bounded and side-effect free; model output alone cannot authorize or execute actions.
- Validation: targeted API/unit negative tests for every remediation and safe rendering tests.
- Completion criterion: no unresolved Critical/High finding; Medium fixes or explicitly accepted residual risks are recorded.
- Dependencies: Stage 1 register and prior prompt/RAG contracts.
- Proposed checkpoint commit: `feat(security): harden llm runtime boundaries`.

### Stage 5 — Adversarial QA, documentation and rollout

- Goal: validate the integrated result, update affected permanent records and close recoverably.
- Status: pending.
- Actions: full proportional automated/manual matrix, bounded thinking/non-thinking comparison if models are available and explicitly safe, canary/rollback verification, docs/changelog/backlog updates, progress cleanup.
- Expected result: specification DoD is checked with exact evidence and clean working tree.
- Validation: static baseline, relevant full suites, API/browser/manual checks and final diff/status audit; skipped external checks explicitly recorded.
- Completion criterion: all acceptance criteria pass or explicitly approved residual limits remain; task artifacts are removed and permanent docs are current.
- Dependencies: Stages 1–4.
- Proposed checkpoint commits: documentation/QA checkpoint, then final cleanup commit removing this file.

## Decisions

### Preserve the pre-existing specification edit

- Context: the working tree contained one modified tracked file before branch creation.
- Decision: treat it as user-owned task input, verify it equals the supplied external specification, and include it in the Stage 1 checkpoint as the authoritative task specification.
- Reason: preserve user work and keep checkpoint ownership reviewable.
- Consequences: the Stage 1 checkpoint will preserve the exact specification that governed the audit; it is not an unrelated edit.

### Stage 1 audit artifact

- Context: the temporary progress file must be deleted at genuine task completion, while audit evidence is an explicit deliverable.
- Decision: keep durable maps, inventories, threat/remediation registers, baseline and rollback plan in `docs/security/PROMPT_RAG_SECURITY_AUDIT.md`; keep execution/checkpoint state here.
- Reason: audit evidence remains reviewable after final progress cleanup without duplicating raw specification or sensitive values.
- Consequences: later stages update the audit report only when a control, finding state or residual risk changes.

### Prompt boundary and persona migration contract

- Context: the former base prompt mixed global security/grounding rules with a default assistant persona, while multiple untrusted sources were distinguished only by labels and RAG was promoted to `system`.
- Decision: keep a compact backend-owned policy plus immutable guard at L1; serialize profile persona/configuration as bounded-influence L2; serialize every mapped evidence/history source as structured L4 data, including forged-boundary escaping. Keep the metadata snapshot value-free.
- Reason: prompt role and source authority must be explicit and testable without logging client values or relying on model obedience.
- Consequences: new/empty profiles receive the versioned default persona. A one-shot migration preserves every non-empty existing profile prompt exactly, marks its origin, and can be rolled back by removing the migration marker without rewriting user text. Live-model behavior remains a Stage 5 validation, not a Stage 2 claim.

## Progress log

### 2026-08-13 16:10 +0300

- Stage: 1.
- Completed: read task specification, root agent guide, skill and required architecture/testing knowledge; verified `dev == origin/dev`; created the authorized feature branch.
- Changed: added this progress file only.
- Validation: external and repository specification copies compare equal; `git rev-list --left-right --count dev...origin/dev` returned `0 0`.
- Issues: documentation read output was truncated; relevant claims will be re-read in bounded sections before implementation.
- Next action: locate verified prompt, chat, RAG, ownership, task, plugin, subprocess, SQLite and rendering entry points and their tests.

### 2026-08-13 Stage 1 complete

- Stage: 1.
- Completed: code-backed prompt/data/action map; asset/retention and entry/sink inventories; 16-item threat register; synthetic grounding baseline; corpus-hygiene gap assessment; red-team fixtures/harness; remediation matrix; rollout/rollback and residual-risk record.
- Changed: authoritative specification, permanent audit report, six synthetic Markdown fixtures, Python audit harness and two Markdown/XSS regression cases.
- Validation: `git diff --check`; Python compileall; `node --check web_ui/js/app.js`; 4/4 Markdown tests; 73 targeted Python chat/RAG/router/security tests passed with 7 intentional expected failures that reproduce open findings.
- Issues: full baseline has three reproducible pre-existing ASR/plugin failures; live models, LAN/tailnet and manual browser matrix were not run in Stage 1.
- Next action: create the focused Stage 1 checkpoint, then implement the prompt boundary contract and profile-persona migration tests for Stage 2.

### 2026-08-13 Stage 1 checkpoint

- Stage: 1.
- Completed: reviewed the staged audit/test/specification diff and created the focused checkpoint.
- Commit: `f01424c` (`test(security): add prompt and rag audit baseline`).
- Validation: cached diff contained only task-owned Stage 1 files; checkpoint completed without rewriting history.
- Issues: none beyond the three recorded pre-existing baseline failures.
- Next action: implement Stage 2 prompt-source boundaries and migration contract.

### 2026-08-13 Stage 2 complete

- Stage: 2.
- Completed: added global policy/immutable guard, L2 profile configuration envelopes, uniform L4 data envelopes for every mapped chat/ASR/OCR/Vision input, evidence-safe history behavior, metadata-only prompt snapshot and versioned default-persona migration that preserves existing prompts.
- Changed: chat prompt policy/composition, ASR analysis composition, derived Vision/OCR context, profile defaults/migration/write metadata, focused regression tests and affected architecture/RAG/backend/security docs.
- Validation: audit harness reports 17 tests successful with four intentional expected failures reserved for Stage 4; combined relevant Python run executed 172 tests with only the two matching pre-existing ASR pipeline failures; `git diff --check`, Python compileall and `node --check web_ui/js/app.js` passed.
- Issues: no new regression found. Structural prompt tests do not substitute for bounded live-model evaluation; claim-level grounding diagnostics remain Stage 3.
- Next action: inspect/stage the complete Stage 2 diff and create `feat(chat): enforce prompt source boundaries`.

## Changed files

### Added

- `docs/progress/prompt-rag-security-hardening-progress.md`.
- `docs/security/PROMPT_RAG_SECURITY_AUDIT.md`.
- `tests/test_prompt_rag_security_audit.py`.
- `tests/fixtures/prompt_rag_security/*.md` (six synthetic fixtures).
- `backend/apps/chat/prompt_policy.py`.

### Modified

- `docs/PROMPT_RAG_SECURITY_AUDIT_SPEC.md` (user-supplied authoritative specification, verified equal to external source).
- `tests/markdown_rendering.test.mjs`.
- `app/db.py`, `app/prompts/system_base.md`, `app/roles.py`, `app/routes/profiles.py`.
- `backend/apps/chat/service.py`, `backend/apps/chat/services/vision_context.py`, `backend/apps/chat/tasks.py`.
- `backend/apps/asr/pipeline.py`.
- `tests/test_chat_vision_context.py`, `tests/test_pipeline_memory.py`, `tests/test_prompt_rag_security_audit.py`.
- `docs/ARCHITECTURE.md`, `docs/knowledge/backend.md`, `docs/knowledge/rag.md`, `docs/security/PROMPT_RAG_SECURITY_AUDIT.md`.

### Deleted

- None.

## Validation results

- Static checks: `git diff --check`, `venv/bin/python -m compileall -q app backend tests`, `node --check web_ui/js/app.js` passed.
- Unit/contract tests: Stage 1 targeted 73 Python tests passed with 7 expected baseline failures and 4 Node Markdown tests passed. Stage 2 audit harness has 17 successes plus 4 expected Stage 4 gaps; the 172-test relevant run has only two matching pre-existing ASR pipeline failures.
- Integration/smoke tests: pending.
- Manual/regression checks: pending.
- Skipped checks and reasons: live model/hardware/network checks deferred until scoped and explicitly safe.
- Remaining uncertainty: live-model obedience to the structural boundary, claim-level grounding/provenance behavior, and current output-sink/resource/ownership gaps assigned to later stages.

## Regressions and deferred work

- New regressions: none known.
- Pre-existing failures: three exact full-suite cases recorded in Baseline; each reproduces in a targeted rerun.
- Unresolved blockers: none.
- Deferred/technical debt: none yet; adjacent findings will not broaden scope.

## Documentation and permanent records

- Architecture/testing/setup docs: permanent security audit added; architecture/testing knowledge updates wait until behavior changes.
- Module knowledge docs: pending later stages.
- Changelog/release notes: pending Stage 5.
- Backlog: update only for actionable deferred findings.
- Canonical project/task index: `docs/CHANGELOG.md` is the repository completion record specified by `AGENTS.md`; no new index will be invented.

## Checkpoints

- Stage 1: `f01424c` (`test(security): add prompt and rag audit baseline`).
- Stage 2 is complete and ready for checkpoint; commit hash pending.

## Continuation state

- Current stage: Stage 2 checkpoint.
- Last completed action: updated affected permanent documentation after passing the focused Stage 2 validation.
- Current repository state: Stage 2 code/test/document changes are unstaged on top of the clean Stage 1 checkpoint.
- Known risks: natural-language envelopes remain defense-in-depth, and migration behavior must not overwrite custom profile prompts.
- Next exact action: inspect the complete Stage 2 diff, stage only task-owned files and create the authorized focused commit.
- Next command or file: `git diff --check`, `git diff`, then `git add` for the Stage 2 file set and cached-diff review.

## Final checklist

- [ ] Every approved stage is completed.
- [ ] Every acceptance criterion and Definition of Done item is checked.
- [ ] Required validation passed or limitations are explicitly accepted.
- [ ] Regressions were compared with baseline.
- [ ] Only affected permanent documentation and records were updated.
- [ ] Deferred work was captured without expanding scope.
- [ ] No unrelated changes or task-owned temporary artifacts remain.
- [ ] Final diff and working-tree state were inspected.
- [ ] Progress file is ready to be deleted.
