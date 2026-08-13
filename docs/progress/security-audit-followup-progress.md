# Security Audit Follow-up Progress

## Task

- Goal: close the residual LocalGPT security risks for profile/session isolation, live Ollama behavior, and real LAN access.
- Problem: the prior Stage 1–4 audit left live-model and LAN validation unverified; the supplemented specification also requires strict chat-session ownership for every derived context path.
- Expected result: backend-enforced isolation, deterministic automated coverage, controlled live-model evidence, and LAN Caddy evidence without public backend binding.
- Source specification: `/Users/oleksandr/Documents/Custom files/Github Repositories/ТЗ для моего обучения/SECURITY_AUDIT_FOLLOWUP_STAGE5_7_v3.md`.
- Branch: `feature/prompt-rag-security-hardening`.
- Started: 2026-08-13.
- Current status: in progress.
- Current stage: Stage 6 — Controlled live-model jailbreak validation.

## Instructions and precedence

- Direct user requirements: continue the completed security audit using the supplemented specification and `$project-progress-workflow`.
- Task-specific requirements: automated profile/session isolation matrix; exact history-turn semantics; controlled live Ollama validation; LAN via Caddy HTTPS and a second device; affected documentation only.
- Applicable AGENTS.md rules: preserve unrelated work, verify claims against code, validate each stage, make focused authorized checkpoints, keep one task progress file, and do not claim live checks that did not run.
- Conflicts and resolutions: the specification contains a malformed/empty remote-access fragment after Stage 3A. Its explicit Future section removes Tailscale and model router from scope, so this continuation maps its three intact workstreams to prior-audit Stage 5, Stage 6, and Stage 7A (LAN only).
- Git authorization: the task specification assigns Implementation/Git to Codex; focused stage commits are authorized. No new branch is needed because the existing feature branch contains the six prior audit checkpoints.

## Scope lock

### In scope

- Profile plus session checks for chat preparation, session APIs, messages, criteria, summaries, transcripts, reasoning, attachments, tasks, diagnostics, and derived RAG sources.
- History setting contract: default 6, 1 turn = completed user/assistant pair, bounded profile persistence, exact current-session selection, no active/failed/cancelled rows.
- Session-scoped Chat/Vision/ASR derived RAG retrieval and lifecycle, with data-preserving handling of existing records.
- Controlled synthetic live-model jailbreak harness/report for an installed Ollama chat model.
- LAN launcher/runtime-port/Caddy/CORS/admin-token contracts and real host plus second-device smoke.
- Affected architecture, backend, RAG, UI, networking, testing, changelog, backlog, and audit follow-up records only.

### Out of scope

- User identity/login/RBAC, public SaaS/network exposure, external agents/tools, new embedding stack, Tailscale validation, model router validation, or broad UI refactoring.
- Automatic promotion of session-derived data to profile-wide RAG. A new promotion UX is not required unless an existing product path depends on it.

### Affected areas and expected files

- `app/db.py`, profile/session schemas and routes.
- `backend/apps/chat/`, `backend/apps/rag/`, and relevant ASR transcript integration.
- Active LLM settings UI and focused Node contract tests.
- LAN launcher/config/status helpers and focused network tests.
- New focused isolation/live-security tests and affected permanent docs.

### Dependencies and compatibility

- Existing SQLite columns already carry `session_id` for RAG documents/chunks; migrations must preserve legacy data.
- Manually managed Markdown RAG remains profile-wide; derived Chat/Vision/ASR is session-owned by default.
- Existing local single-owner profile model remains; this task does not add authenticated principals.
- Ollama and Caddy binaries are installed; actual local sockets/network clients require controlled live access.

### Risks and rollback concerns

- Filtering legacy derived records with missing session ownership could make ambiguous data disappear from retrieval; safer quarantine is preferred over cross-session exposure.
- Pair-aware history must not include active or failed assistant rows and must not break history display APIs.
- LAN fixes must never fall back to a default `0.0.0.0` backend bind or wildcard CORS.
- Model output is nondeterministic; hard pass/fail is based on protected input/action boundaries, not refusal wording alone.

## Baseline

- Current behavior: chat request preparation accepts a known session and replaces the request profile with the session profile; RAG search filters by profile only; `get_messages(limit_pairs=N)` takes the last `2N` rows rather than completed conversation pairs.
- Existing positive controls: summaries, transcripts, attachments, reasoning, and task lifecycle already carry session identifiers in major paths; task events/status/cancel require profile plus session; default `mem_turns` is 6 and profile-owned.
- Existing tests: 162 relevant Python tests run before edits.
- Validation commands: focused Python/Node/shell checks per stage, then project static baseline and full discovery.
- Pre-existing failures: `test_full_analysis_skips_cleaner_by_default_and_sanitizes_speakers`; `test_pipeline_tasks_are_normalized_for_transcript_record`; full-suite-only plugin DB restore failure from the prior audit baseline.
- Branch and working-tree state: `feature/prompt-rag-security-hardening` at `4d20614`; clean before this progress file.
- Unrelated user changes to preserve: none detected. `docs/progress/.gitkeep` remains.

## Architecture

- Current flow: profile-scoped settings feed a session-based prompt, but several API lookups trust object IDs and derived RAG retrieval ignores the stored session key.
- Target flow: every session-owned lookup requires a matching active profile and session; RAG selection admits profile-wide rows plus derived rows owned by the active session only.
- Contracts and boundaries: foreign and unknown identifiers share a safe not-found/denied contract; backend enforcement is authoritative and prompt language is defense-in-depth.
- Data and ownership: backend/global policy → profile preferences/manual RAG → session messages, summaries, criteria, transcripts, reasoning, attachments, tasks, and derived RAG.

## Implementation stages

### Stage 5 — Profile and chat-session isolation

- Goal: enforce and prove consistent profile/session ownership and exact history-turn behavior.
- Status: completed.
- Actions: add an isolation matrix; implement pair-aware prompt history; require matching profile/session at chat and session-owned APIs; filter session-derived RAG; preserve lifecycle cleanup; update affected contracts/docs.
- Expected result: a new chat receives only profile-wide resources and its own session data.
- Validation: focused isolation, chat/RAG, attachment, task, pipeline, UI-setting, compile/static tests; compare with baseline.
- Completion criterion: all context sources and lifecycle paths in the specification have deterministic cross-profile/cross-session tests with no new failure.
- Affected files: DB/repositories, chat/RAG/routes/schemas/UI, tests, affected docs.
- Dependencies: existing Stage 1–4 security controls and SQLite scope columns.
- Proposed checkpoint commit: `feat(security): enforce profile and session context isolation`.

### Stage 6 — Controlled live-model jailbreak validation

- Goal: run the prior security controls against an actually installed Ollama chat model with synthetic canaries.
- Status: pending.
- Actions: add a separate opt-in harness/command; record model/runtime identity and hard/behavioral classifications; run bounded deterministic fixtures; make minimal mitigation only for reproduced failures.
- Expected result: reproducible live report without raw hidden prompts, client corpus, or secrets.
- Validation: harness unit tests plus controlled repeated live run; confirm no foreign source reaches request and no model output triggers a privileged action.
- Completion criterion: hard cases disclose no protected canary and create no action edge; behavioral limitations are mitigated or explicitly residual.
- Affected files: test/harness, testing docs, audit follow-up; prompt policy only if evidence requires it.
- Dependencies: Stage 5 isolation complete and Ollama runtime access.
- Proposed checkpoint commit: `test(security): add controlled live model validation`.

### Stage 7A — LAN Caddy validation

- Goal: validate/fix Caddy HTTPS → localhost backend with actual runtime port and private LAN address.
- Status: pending.
- Actions: automate launcher/config negative contracts; run host smoke; verify same-origin UI/API/SSE/admin authorization; complete second-device smoke; update only factual networking docs.
- Expected result: LAN works without public backend bind, wildcard CORS, stale runtime targets, or leaked key material.
- Validation: shell/unit tests, host curl/SSE/static/admin checks, and documented second-device matrix.
- Completion criterion: host and second-device UI, health/API, SSE pass; missing token is denied; backend remains localhost.
- Affected files: launcher/network helpers/tests/docs if defects are found.
- Dependencies: Caddy, private LAN IP, trusted client certificate, second device, configured `ADMIN_TOKEN` for the positive privileged case.
- Proposed checkpoint commit: `fix(networking): validate secure LAN runtime path`.

### Stage 8 — Regression, records, and cleanup

- Goal: recheck every acceptance criterion and close temporary execution state.
- Status: pending.
- Actions: full proportional regression; update affected permanent docs/audit/changelog/backlog; inspect complete history/status; delete this progress file only after all required live evidence exists.
- Expected result: exact revision/environment evidence, no new regressions, clean working tree.
- Validation: static baseline, full Python and Node suites, final diff/status/log inspection.
- Completion criterion: Definition of Done satisfied and cleanup checkpoint created.
- Affected files: affected permanent docs and this progress file.
- Dependencies: Stages 5–7A complete.
- Proposed checkpoint commit: `chore(progress): close security audit follow-up`.

## Decisions

### Treat ambiguous legacy derived sources as non-retrievable across chats

- Context: pre-existing derived RAG rows may lack reliable session ownership.
- Decision: never infer profile-wide authority from missing `session_id`; keep data but exclude ambiguous derived rows from ordinary chat retrieval until explicitly re-created/promoted.
- Reason: preservation without leakage is safer than implicit scope widening.
- Alternatives: treat all legacy rows as profile-wide (unsafe), or delete them (destructive).
- Consequences: some legacy derived context may require explicit user re-export.

### History means completed pairs

- Context: current code multiplies `mem_turns` by two rows.
- Decision: prompt history selects up to N chronological completed `user + assistant` pairs from the active session; the current query is not counted.
- Reason: matches the supplemented specification and UI semantics.
- Alternatives: keep row-count semantics (rejected).
- Consequences: history display can keep its independent all-message contract.

## Progress log

### 2026-08-13 — continuation baseline

- Stage: Stage 5.
- Completed: read the supplemented specification, workflow, prior audit, required architecture/testing/backend/RAG/provider/network/UI/backlog documents; traced history/RAG/LAN entry points.
- Changed: created this progress checkpoint only.
- Validation: 162 relevant tests ran; two known ASR failures reproduced, all selected chat/RAG/runtime-security tests passed. `/bin/zsh -n tools/LTrnsrb.sh` passed.
- Issues: Ollama local socket is blocked inside the default sandbox; second-device LAN evidence is external and remains pending.
- Next action: add deterministic Stage 5 isolation tests that expose the three confirmed boundary defects before implementing fixes.

### 2026-08-13 — Stage 5 isolation checkpoint

- Stage: Stage 5.
- Completed: enforced matching profile/session across chat preparation, session messages/criteria, transcripts/pipeline, reasoning, attachments, tasks and derived RAG; implemented completed-pair history with `0/1/6/100` persistence; made Chat/Vision/ASR sources session-only; added eager session-derived index cleanup and UI scope propagation.
- Changed: backend/database/RAG/ASR/UI contracts, deterministic Python/Node isolation tests, and affected architecture/backend/RAG/UI/testing/changelog records.
- Validation: 216 focused Python tests ran with only the two recorded ASR baseline failures; 28 Node tests, compileall, JS syntax, and diff check passed.
- Issues: ambiguous legacy derived rows without `session_id` are preserved but quarantined from ordinary retrieval; explicit promotion remains out of scope.
- Next action: create the Stage 5 checkpoint, then build the opt-in live Ollama security harness.

## Changed files

### Added

- `docs/progress/security-audit-followup-progress.md`.
- `tests/test_context_isolation.py`.
- `tests/context_isolation_ui.test.mjs`.

### Modified

- `app/db.py`, session/criteria schemas and routes.
- Chat attachments/routes/service and ASR transcript/pipeline routes.
- RAG routes/service and active Web UI request/settings flows.
- Existing focused tests and affected permanent documentation.

### Deleted

- None.

## Validation results

- Static checks: compileall, JS syntax, diff check, and launcher zsh syntax passed.
- Unit/contract tests: Stage 5 matrix passed; 216 broad focused tests reproduced only two baseline ASR failures; 28 Node tests passed.
- Integration/smoke tests: not started.
- Manual/regression checks: not started.
- Skipped checks and reasons: live Ollama and LAN intentionally deferred until isolated automated controls are implemented.
- Remaining uncertainty: live model behavior and real LAN remain unverified; ambiguous legacy derived rows are quarantined without an automatic promotion/migration.

## Regressions and deferred work

- New regressions: none.
- Pre-existing failures: two ASR tests in focused baseline; prior full-suite plugin DB restore issue.
- Resolved issues: row-based history semantics, profile/session ID substitution, cross-session derived retrieval/deletion, and session-owned object API gaps.
- Unresolved blockers: second-device LAN access is required before Stage 7A can close.
- Deferred/technical debt: Tailscale, model router, authenticated multi-user identity, and promotion UX remain separate scope.

## Documentation and permanent records

- Architecture/testing/setup docs: `ARCHITECTURE.md` and `TESTING.md` updated for Stage 5.
- Module knowledge docs: backend/RAG/UI updated; networking remains pending Stage 7A.
- Changelog/release notes: Unreleased records session isolation and exact history semantics.
- Backlog: remove or refine the now-active live/LAN item only after completion; preserve explicit future Tailscale work.
- Canonical project/task index: security audit follow-up section is the permanent evidence record.

## Checkpoints

- Prior audit checkpoints: `f01424c`, `fead0e5`, `6788daf`, `1a03d3f`, `bd76dc1`, `4d20614`.
- Follow-up checkpoints: none yet.

## Continuation state

- Current stage: Stage 6.
- Last completed action: Stage 5 implementation, focused regression, and affected-doc update.
- Current repository state: Stage 5 diff ready for focused commit; progress file remains ignored until forced add.
- Known risks: live model behavior and LAN environment are still unverified; legacy derived rows are intentionally non-retrievable without ownership.
- Next exact action: checkpoint Stage 5, then add a separate opt-in synthetic live-model harness.
- Next command or file: inspect staged Stage 5 diff, commit, then trace `ollama_runtime` request metadata for the live harness.

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
