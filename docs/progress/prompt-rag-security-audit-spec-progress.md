# Prompt, RAG, and Security Audit Specification Progress

## Task

- Goal: prepare an implementation-ready specification for auditing and hardening RAG grounding, prompt composition, system prompts, and LLM-facing security boundaries.
- Problem: a real RAG answer narrowed supported CMS to one product, treated prior assistant text as evidence, and mixed retrieved facts with assumptions; current prompt layers do not explicitly classify untrusted data or cover the requested injection/leakage/resource/execution/external-agent threats.
- Expected result: one canonical specification with scope, threat model, audit method, implementation stages, acceptance criteria, red-team matrix, and mandatory new-branch workflow.
- Source specification: user request and two accepted response annotations from 2026-08-13.
- Branch: `feature/chat-thinking-reasoning-rag` for documentation only; future implementation must create a new feature branch.
- Started: 2026-08-13.
- Current status: in_progress.
- Current stage: Stage 2 — cleanup.

## Instructions and precedence

- Direct user requirements: close the prior task; prepare the new audit/remediation specification; include system prompt security, direct/indirect injection, leakage, resource abuse, unsafe response execution, and malicious external-agent instructions; require a new Git branch in the specification.
- Applicable AGENTS.md rules: planning reads `docs/BACKLOG.md`; substantial documentation uses one progress file and focused checkpoints; no branch is created without explicit request.
- Conflicts and resolutions: the requested new branch is a requirement for future implementation, not permission to create one for this documentation-only task.
- Git authorization: repository workflow requires stage checkpoints; no push or PR requested.

## Scope lock

### In scope

- Grounding/source-trust policy, RAG retrieval quality, prompt hierarchy, system/profile prompts, data leakage, resource controls, response sinks, tool/SQL/process boundaries, and external-agent data.
- Measurable audit artifacts, remediation stages, tests, rollout/rollback, and Definition of Done.

### Out of scope

- Implementing the controls now, importing client RAG data into the repository, live penetration testing, public exposure, or adding email/external-agent integrations.

### Affected areas and expected files

- `docs/PROMPT_RAG_SECURITY_AUDIT_SPEC.md`, `docs/README.md`, `docs/BACKLOG.md`, and this temporary progress file.

### Risks and rollback concerns

- Prompt-only controls could create false confidence; the spec must require code-enforced boundaries and negative tests.
- Security logging must not persist system prompts, secrets, private RAG text, or raw client data.

## Baseline

- Prior task is closed at `2362989`; working tree was clean before this task.
- Base prompt only has general non-fabrication guidance.
- Profile prompt and retrieved RAG are inserted as system-role messages; profile context, memory, transcripts, criteria, history, and current query are composed without a formal trust taxonomy.
- RAG uses deterministic `local-hash-v1`, top-k retrieval, 1200-character chunks and 180-character overlap; semantic quality is known to depend on explicit headings and keywords.
- Existing RAG prompt says missing facts must not be invented, but does not forbid assistant-history self-citation or define supported/unsupported/inferred claims.
- Full Python suite has three documented pre-existing problems unrelated to this documentation task.

## Implementation stages

### Stage 1 — Canonical specification

- Goal: create and validate the audit/remediation contract and link it from canonical planning docs.
- Status: completed.
- Validation: requirement traceability review, Markdown/link/path checks, `git diff --check`, complete diff inspection.
- Completion criterion: every user threat category, both annotations, new-branch rule, stages, acceptance criteria, and explicit exclusions are represented.
- Proposed checkpoint commit: `docs: specify prompt rag security audit`.

### Stage 2 — Cleanup

- Goal: remove temporary execution state after the specification is checkpointed.
- Status: in_progress.
- Validation: clean worktree and final log/status inspection.
- Completion criterion: progress file removed, permanent spec/backlog retained, repository state understood.
- Proposed checkpoint commit: `chore: close prompt rag security spec progress`.

## Decisions

### Layered security, not prompt-only safety

- Decision: require prompt policy, provenance-aware context construction, bounded runtime controls, safe sinks, authorization checks, and adversarial tests.
- Reason: untrusted content can influence model output even when a system prompt says not to follow it.

### Previous assistant output is not evidence

- Decision: history can provide conversational continuity but cannot establish company facts unless independently supported by an approved source in the current request.
- Reason: this is the observed grounding failure.

## Progress log

### 2026-08-13 — analysis and baseline

- Stage: Stage 1 in progress.
- Completed: prior task closure verified; skill/template and required planning/architecture/RAG/backend/testing docs read; prompt composition and execution surfaces inspected.
- Changed: this progress file only.
- Validation: repository clean at task start.
- Next action: write the canonical specification and planning links.

### 2026-08-13 — canonical specification

- Stage: Stage 1 completed; Stage 2 started.
- Completed: implementation-ready specification covering the accepted CMS/regions grounding scenario, assistant-history self-citation prohibition, trust hierarchy, system prompt audit, direct/indirect injection, leakage, resource abuse, safe output sinks, external-agent threats, staged remediation, tests, acceptance criteria, and mandatory new feature branch.
- Changed: canonical specification, documentation index, backlog, and this progress file.
- Validation: requirement traceability search, Markdown/path review, `git diff --check`, complete diff inspection.
- Issues: none; future connector inventory remains intentionally conditional on the implementation base commit.
- Next action: create the Stage 1 checkpoint, then remove this temporary progress file in cleanup.

## Validation results

- Static checks: `git diff --check` passed; required sections and permanent links verified.
- Unit/contract tests: not applicable to documentation-only work.
- Integration/smoke tests: skipped; no runtime behavior changes.
- Remaining uncertainty: implementation audit must inventory any future connectors/tools present when its new branch is created.

## Continuation state

- Current stage: Stage 2 cleanup.
- Last completed action: specification traceability and diff validation.
- Current repository state: permanent specification diff ready for Stage 1 checkpoint; progress file is ignored until force-added.
- Known risks: none for documentation; future implementation must re-audit actual connectors and base commit.
- Next exact action: checkpoint Stage 1, delete the completed progress file, and create cleanup checkpoint.

## Final checklist

- [x] Every approved specification requirement is represented.
- [x] Required validation passed or limitations are explicitly accepted.
- [x] Only affected permanent documentation and records were updated.
- [x] No unrelated changes were introduced.
- [x] Final Stage 1 diff and working-tree state were inspected.
- [x] Progress file is ready to be deleted after the Stage 1 checkpoint.
