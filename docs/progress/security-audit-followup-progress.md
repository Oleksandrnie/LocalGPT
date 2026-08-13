# Security Audit Follow-up Progress

## Task

- Goal: close the residual LocalGPT security risks for profile/session isolation, live Ollama behavior, and real LAN access.
- Problem: the prior Stage 1–4 audit left live-model and LAN validation unverified; the supplemented specification also requires strict chat-session ownership for every derived context path.
- Expected result: backend-enforced isolation, deterministic automated coverage, controlled live-model evidence, and LAN Caddy evidence without public backend binding.
- Source specification: `/Users/oleksandr/Documents/Custom files/Github Repositories/ТЗ для моего обучения/SECURITY_AUDIT_FOLLOWUP_STAGE5_7_v3.md`.
- Branch: `feature/prompt-rag-security-hardening`.
- Started: 2026-08-13.
- Current status: in progress.
- Current stage: Stage 10 pending — hybrid lexical and semantic candidate fusion.

## Instructions and precedence

- Direct user requirements: continue the completed security audit using the supplemented specification and `$project-progress-workflow`; extend the work to domain-independent semantic RAG, execute exactly one stage per continuation, commit it, and stop until the user manually resumes.
- Task-specific requirements: automated profile/session isolation matrix; exact history-turn semantics; controlled live Ollama validation; LAN via Caddy HTTPS and a second device; affected documentation only.
- Applicable AGENTS.md rules: preserve unrelated work, verify claims against code, validate each stage, make focused authorized checkpoints, keep one task progress file, and do not claim live checks that did not run.
- Conflicts and resolutions: the specification contains a malformed/empty remote-access fragment after Stage 3A. Its explicit Future section removes Tailscale and model router from scope, so this continuation maps its three intact workstreams to prior-audit Stage 5, Stage 6, and Stage 7A (LAN only). The original scope excluded a new embedding stack; the user's later explicit request expands Stage 7C into a staged, domain-independent semantic-RAG continuation, which takes precedence. No corpus/company-specific retrieval rules are allowed.
- Git authorization: the task specification assigns Implementation/Git to Codex; focused stage commits are authorized. No new branch is needed because the existing feature branch contains the six prior audit checkpoints.

## Scope lock

### In scope

- Profile plus session checks for chat preparation, session APIs, messages, criteria, summaries, transcripts, reasoning, attachments, tasks, diagnostics, and derived RAG sources.
- History setting contract: default 6, 1 turn = completed user/assistant pair, bounded profile persistence, exact current-session selection, no active/failed/cancelled rows.
- Session-scoped Chat/Vision/ASR derived RAG retrieval and lifecycle, with data-preserving handling of existing records.
- Controlled synthetic live-model jailbreak harness/report for an installed Ollama chat model.
- LAN launcher/runtime-port/Caddy/CORS/admin-token contracts and real host plus second-device smoke.
- Affected architecture, backend, RAG, UI, networking, testing, changelog, backlog, and audit follow-up records only.
- Domain-independent retrieval evaluation, local multilingual embedding provider/versioning, hybrid candidate fusion, optional local reranking, bounded context packing, reindex lifecycle, and proportional sequential validation.

### Out of scope

- User identity/login/RBAC, public SaaS/network exposure, external agents/tools, Tailscale validation, model router validation, broad UI refactoring, corpus-specific brands/phrases, and tuning production policy to the temporary work corpus.
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
- Status: completed.
- Actions: add a separate opt-in harness/command; record model/runtime identity and hard/behavioral classifications; run bounded deterministic fixtures; make minimal mitigation only for reproduced failures.
- Expected result: reproducible live report without raw hidden prompts, client corpus, or secrets.
- Validation: harness unit tests plus controlled repeated live run; confirm no foreign source reaches request and no model output triggers a privileged action.
- Completion criterion: hard cases disclose no protected canary and create no action edge; behavioral limitations are mitigated or explicitly residual.
- Affected files: test/harness, testing docs, audit follow-up; prompt policy only if evidence requires it.
- Dependencies: Stage 5 isolation complete and Ollama runtime access.
- Proposed checkpoint commit: `test(security): add controlled live model validation`.

### Stage 7A — LAN Caddy validation

- Goal: validate/fix Caddy HTTPS → localhost backend with actual runtime port and private LAN address.
- Status: in progress; host and second-device functionality passed, iPhone certificate trust remains pending.
- Actions: automate launcher/config negative contracts; run host smoke; verify same-origin UI/API/SSE/admin authorization; complete second-device smoke; update only factual networking docs.
- Expected result: LAN works without public backend bind, wildcard CORS, stale runtime targets, or leaked key material.
- Validation: shell/unit tests, host curl/SSE/static/admin checks, and documented second-device matrix.
- Completion criterion: host and second-device UI, health/API, SSE pass; missing token is denied; backend remains localhost.
- Affected files: launcher/network helpers/tests/docs if defects are found.
- Dependencies: Caddy, private LAN IP, trusted client certificate, second device, configured `ADMIN_TOKEN` for the positive privileged case.
- Proposed checkpoint commit: `fix(networking): validate secure LAN runtime path`.

### Stage 14 — Regression, records, and cleanup

- Goal: recheck every acceptance criterion and close temporary execution state.
- Status: pending.
- Actions: full proportional regression; update affected permanent docs/audit/changelog/backlog; inspect complete history/status; delete this progress file only after all required live evidence exists.
- Expected result: exact revision/environment evidence, no new regressions, clean working tree.
- Validation: static baseline, full Python and Node suites, final diff/status/log inspection.
- Completion criterion: Definition of Done satisfied and cleanup checkpoint created.
- Affected files: affected permanent docs and this progress file.
- Dependencies: Stages 5–13 complete.
- Proposed checkpoint commit: `chore(progress): close security audit follow-up`.

### Stage 7B — Thinking OFF, follow-up RAG, and mobile controls

- Goal: correct the defects reproduced during second-device QA without changing user data or introducing silent model fallback.
- Status: completed; checkpoint pending.
- Actions: keep Qwen hybrid reasoning structurally separated when OFF is requested; reject reasoning-only/truncated completion; expand short referential RAG follow-ups using authorized recent user queries and improve generic platform relevance; cover both mobile Thinking controls and 44 px tap targets.
- Expected result: OFF never shows/stores model reasoning as final content, generic `other CMS` follow-ups retrieve explicit corpus evidence, and both mobile controls remain synchronized.
- Validation: focused provider/chat/RAG Python tests, Node UI contracts, 390x844 manual browser matrix, then one bounded sequential `qwen3:4b` live smoke with final `keep_alive=0`.
- Completion criterion: deterministic regressions pass; live OFF returns only final content or an explicit fail-closed error, never reasoning-as-content; no unrelated/user runtime data is modified.
- Affected files: Ollama runtime/chat service/task handling, RAG query preparation/ranking helpers, active UI CSS/tests, and affected provider/RAG/UI/testing records.
- Dependencies: confirmed local manifest behavior, existing Stage 5 isolation, Stage 6 output boundary, and preserved Stage 7A LAN changes.
- Proposed checkpoint commit: `fix(chat): harden thinking off and follow-up retrieval`.

### Stage 7C — Cross-model RAG grounding parity

- Goal: determine why `qwen2.5:3b-instruct` and `qwen2.5:7b-instruct` use the same RAG evidence less completely than the validated Qwen3 path.
- Status: in progress; 3B checkpoint complete, Qwen3 short-confirmation follow-up corrected, 7B intentionally deferred to the next bounded run.
- Actions: compared metadata-only retrieved chunk IDs and effective settings; ran 3B sequentially without chat persistence; changed shared RAG query composition so explicit topics retain only lexically relevant user-history turns while short/deictic or three-word confirmation follow-ups retain the latest turn. Do not add corpus brands or a per-model prompt.
- Expected result: every supported chat model receives the same authorized RAG evidence; unrelated history cannot dilute an explicit current topic; model-specific answer-quality limits are measured and distinguished from retrieval/prompt defects.
- Validation: deterministic shared-RAG prompt tests plus one bounded sequential run per requested model, unloading each before the next.
- Completion criterion: retrieval/prompt parity is proven, direct capability evidence is represented in each response or an explicit evidence-backed model limitation is recorded without hardcoding corpus brands into production policy.
- Affected files: chat RAG query preparation, RAG knowledge contract, focused security/RAG regression tests, active progress record.
- Dependencies: Stage 7A/7B checkpoint committed and all models kept sequential to protect Mac thermals.
- Proposed checkpoint commit: to be determined after diagnosis.

### Stage 7D — Universal RAG context packing

- Goal: ensure selected evidence, rather than the first long chunk or verbose diagnostics, receives the bounded prompt budget.
- Status: completed.
- Actions: compact oversized diagnostics to facet/status metadata; divide remaining characters across all selected non-empty chunks; preserve provenance and an explicit truncation marker; add domain-neutral regressions and update the RAG contract.
- Expected result: when headers fit, every selected chunk contributes evidence within `rag_max_context_chars`, independent of corpus content or downstream LLM.
- Validation: focused prompt/RAG-security tests, real-corpus metadata-only packing observation, compileall, and diff check. No model run.
- Completion criterion: bounded context includes every selected synthetic and real-test chunk; oversized diagnostics cannot starve evidence; Stage 7D introduces no corpus-specific code.
- Affected files: RAG context builder, focused regression tests, RAG knowledge document, active progress record.
- Dependencies: Stage 7C diagnosis and user rejection of corpus-specific ranking rules.
- Proposed checkpoint commit: `fix(rag): distribute context budget across evidence`.

### Stage 8 — Domain-independent retrieval evaluation baseline

- Goal: measure retrieval quality before choosing or integrating a semantic model.
- Status: completed.
- Actions: add small synthetic corpora from multiple unrelated domains, paraphrase/typo/negative/conflict queries, and metadata-only recall@k/MRR/context-inclusion/resource metrics; record current hashing/lexical baseline.
- Expected result: future retrieval changes are accepted by cross-domain evidence rather than one company corpus.
- Validation: deterministic offline eval tests and bounded performance check.
- Completion criterion: repeatable baseline exposes semantic misses without real/client text in repository artifacts.
- Proposed checkpoint commit: `test(rag): add cross-domain retrieval baseline`.

### Stage 9 — Local multilingual embedding infrastructure

- Goal: replace hashing as semantic evidence with a versioned local multilingual embedding provider while preserving explicit offline behavior.
- Status: completed.
- Actions: select a resource-bounded model using primary model documentation; add provider abstraction and dependency/resource gates; persist provider/model/version/dimension; implement explicit reindex requirement and rollback to the previous indexed generation without silent fallback.
- Expected result: arbitrary supported-language chunks and queries receive comparable semantic vectors; stale/incompatible vectors are never mixed.
- Validation: provider contract tests, deterministic stub vectors, schema/reindex/rollback tests, then one bounded local provider smoke if the model is available or download is separately authorized.
- Completion criterion: versioned embeddings can index/search a temporary corpus and unload/release resources predictably.
- Proposed checkpoint commit: `feat(rag): add versioned local embeddings`.

### Stage 10 — Hybrid lexical and semantic candidate fusion

- Goal: retrieve relevant evidence through both exact terminology and paraphrased meaning.
- Status: pending.
- Actions: retrieve lexical and semantic candidate pools, normalize and fuse ranks with a domain-neutral method, preserve provenance/diagnostics, diversity and ownership filters, expose rollback to lexical-only retrieval, and remove the earlier CMS/capability-specific lexical bonus once the cross-domain quality gate passes.
- Expected result: cross-domain eval improves without degrading exact identifiers, profile/session isolation, conflicts, or negative queries.
- Validation: Stage 8 eval comparison, isolation/security regressions, bounded latency/memory measurement.
- Completion criterion: predefined cross-domain quality gate passes and no category relies on corpus-specific vocabulary.
- Proposed checkpoint commit: `feat(rag): fuse lexical and semantic retrieval`.

### Stage 11 — Optional universal reranker with resource gates

- Goal: reorder a bounded candidate set by query-evidence relevance when hybrid fusion alone remains insufficient.
- Status: pending.
- Actions: decide from Stage 10 metrics whether reranking is justified; if yes, add a small local multilingual reranker over top-N with model/version metadata, time/memory limits, explicit unavailable state, and deterministic adapter tests; if no, mark the stage completed with evidence and no code commit.
- Expected result: top-5 precision improves across unrelated domains without keeping a heavy model resident or invoking the chat LLM.
- Validation: before/after Stage 8 metrics, bounded local smoke, unavailable/timeout tests, sequential resource observation.
- Completion criterion: measurable quality gain exceeds the recorded resource cost; otherwise reranker is rejected rather than added by assumption.
- Proposed checkpoint commit if implemented: `feat(rag): add bounded local reranking`.

### Stage 12 — Reindex lifecycle and operational integration

- Goal: make semantic indexing understandable and safely operable for arbitrary replacement corpora.
- Status: pending.
- Actions: expose index provider/version/status and explicit reindex progress/error state through existing RAG APIs/UI where needed; ensure deletion/replacement invalidates the correct index generation; document offline setup and rollback.
- Expected result: replacing the temporary work corpus requires only ordinary delete/upload/reindex actions, with no code change.
- Validation: API/UI contracts, lifecycle integration tests, mobile/desktop status checks if UI changes, static checks.
- Completion criterion: users can identify stale/ready/failed index state and recover without editing code or database rows.
- Proposed checkpoint commit: `feat(rag): expose semantic reindex lifecycle`.

### Stage 13 — Sequential model validation

- Goal: prove that shared retrieval supplies stable evidence to supported chat models.
- Status: pending.
- Actions: run cross-domain deterministic suite, then strictly sequential bounded 3B, 7B and 4B smokes with unload verification; separate retrieval metrics from generation quality.
- Expected result: retrieval behavior is model-independent; remaining LLM limitations are recorded honestly; repository returns clean.
- Validation: metadata-only eval report and sequential live observations with loaded-model checks.
- Completion criterion: accepted quality/resource gates pass and no model overlap occurs; remaining generation limitations are recorded separately from retrieval.
- Proposed checkpoint commit: `test(rag): validate retrieval across local models`.

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
- Checkpoint: `5acb521 feat(security): enforce profile and session context isolation`.
- Next action: build and validate the opt-in live Ollama security harness.

### 2026-08-13 — Stage 6 pre-live harness

- Stage: Stage 6.
- Completed: added a separate opt-in synthetic jailbreak harness with eight required categories, unique protected/behavioral/foreign-scope canaries, deterministic generation settings, metadata-only reporting, and explicit hard-versus-behavioral classification.
- Changed: `tools/live_llm_security.py`, `tests/test_live_llm_security_harness.py`, and this progress record.
- Validation: 49 focused isolation/prompt/runtime/harness tests, compileall, JS syntax, Markdown rendering, and diff check passed.
- Issues: no code regression; the earlier mistyped test module name was corrected in the command and the intended suite passed.
- Next action: identify the installed primary chat model and run the bounded live suite twice through the real Ollama runtime.

### 2026-08-13 — Stage 6 live-model validation and mitigation

- Stage: Stage 6.
- Completed: ran eight synthetic security categories twice on `qwen3:4b`, `qwen2.5:3b-instruct`, and `qwen2.5:7b-instruct`, strictly sequentially; separated raw model behavior from the enforced backend boundary; added normal/reasoning/streaming/vision protected-literal fail-closed handling and removed a reproduced user-marker false positive.
- Changed: backend/profile guard policy, ChatService/task output enforcement, opt-in metadata-only harness/tests, and affected architecture/provider/testing/audit/changelog/backlog records.
- Validation: final current-code runs were `qwen3:4b` 2 raw disclosures / 2 backend blocks / 0 hard failures / 12 behavioral; `qwen2.5:3b-instruct` 2 / 2 / 0 / 6; `qwen2.5:7b-instruct` 0 / 0 / 0 / 6. All 48 runs had no foreign-scope prompt boundary breach or action edge. Ollama `0.32.5`, Metal M1 Pro, `temperature=0`, `num_ctx=8192`, `max_tokens=160`, `think=false`.
- Regression: 201 broad focused Python tests reproduced only the two documented ASR baseline failures; 28 Node tests, compileall, JavaScript syntax, and diff check passed.
- Issues: all three models retain some behavioral susceptibility, strongest on `qwen3:4b`; backend boundaries remain authoritative. No raw prompt, response or canary value was persisted in project artifacts.
- Checkpoint: `5faa232 test(security): add controlled live model validation`.
- Next action: validate the private HTTPS path on the host and then from a second device on the same Wi-Fi network.

### 2026-08-13 — Stage 7A host LAN validation

- Stage: Stage 7A.
- Completed: fixed generated Caddy configuration to bind only the detected private IP, disabled the implicit port-80 redirect listener, made IP/upstream changes force a restart, and added a no-browser launcher mode plus focused negative contracts. Ran the actual localhost backend and project-scoped Ollama behind Caddy.
- Host evidence: backend listened only on `127.0.0.1:8000`; Caddy listened only on `192.168.0.100:8443`; generated config validated with the actual upstream. HTTPS health, UI/static, profiles/models, allowed/denied CORS, privileged API denial and temporary-token success, public-root-CA response, synthetic SSE, and a real sequential `qwen2.5:3b-instruct` SSE request all passed. The user confirmed the visible UI, models, and profiles recovered and work.
- Validation: `tests.test_lan_launcher` and `tests.test_network_certificate` passed (7 tests); launcher shell syntax, Python compilation, and diff check passed.
- Issues: a backend started as a detached child of the Codex command was reaped when that command ended, temporarily producing Caddy 502 responses. This is an execution-environment artifact, not evidence of a normal Terminal launcher defect. No stored models, profiles, or messages were lost.
- Next action: complete the mandatory phone/tablet smoke over `https://192.168.0.100:8443`, including UI/API, health, SSE, certificate trust, and missing-admin-token denial.

### 2026-08-14 — Stage 7C 3B grounding checkpoint

- Stage: Stage 7C, first bounded model pass.
- Finding: `qwen2.5:3b-instruct`, `qwen2.5:7b-instruct`, and `qwen3:4b` use the same effective RAG boundary in the inspected profile (`rag_enabled`, top-5 retrieval, and 6,000-character context). The observed weak answers were not caused by a 3B-only RAG integration.
- Root cause addressed: the former query composer appended up to three prior user turns unconditionally. A real session therefore mixed an explicit CMS request with unrelated earlier topics, widening retrieval diagnostics and diluting evidence for smaller models. The common composer now retains history only when it shares meaningful terms with the explicit current topic; a short or deictic follow-up still gets its newest context turn.
- Live validation: one clean, non-persistent sequential `qwen2.5:3b-instruct` request with the profile RAG boundary, Thinking off, and a 512-token cap completed with `stop`; it produced no exposed reasoning, covered 6/7 expected supported-platform terms, introduced no observed unconfirmed platform, and unloaded successfully (`loaded_after=[]`). Two prior identical attempts also unloaded successfully but their local metadata printer failed after completion; neither wrote a message, changed settings, nor loaded another model.
- Regression: `tests.test_prompt_rag_security_audit` plus `tests.test_model_router` passed (92 tests); chat/test compilation and `git diff --check` passed. Test-time local-Ollama access remained sandbox-blocked only inside mocked unit checks, without a test failure.
- Checkpoint: pending this stage commit.
- Next action: restart the backend onto this committed code, then perform one real-phone CMS follow-up using 3B. Only after that result is recorded, run the equivalent bounded 7B pass; unload before any model switch.

### 2026-08-14 — Stage 7C Qwen3 short-confirmation correction

- Stage: Stage 7C shared follow-up handling.
- Finding: three separate sessions with the same initial CMS question were used for 3B, 7B and Qwen3. The Qwen3 failure followed the three-word confirmation “точно, проверь информацию”: the former short-follow-up threshold excluded the preceding CMS turn, leaving a generic retrieval query that selected unrelated chunks and reported `conflict`.
- Correction: the common composer now treats a three-term confirmation as a short follow-up, retaining its latest authorized user turn. On the recorded Qwen3 session, the composed query now includes the preceding CMS question; selected metadata includes direct capability evidence and diagnostics change to `supported`.
- Validation: 30 focused prompt/RAG-security tests, chat/test compilation and `git diff --check` passed. No model was loaded for this correction and no chat/profile data was changed.
- Profile-prompt check: the stored profile prompt ends cleanly at its self-check section and does not contain the code-oriented text visible after the pasted attachment; that text is a copy artifact, not a runtime instruction.
- Checkpoint: pending this focused commit.
- Next action: restart backend to load this commit; the user rechecks the Qwen3 confirmation in its existing session. Keep 7B deferred until this result is recorded.

### 2026-08-14 — Stage 7D universal context-packing checkpoint

- Stage: Stage 7D.
- Completed: removed the rejected corpus-specific ranking experiment before commit; compacted oversized diagnostics to domain-neutral facet/status metadata; divided the remaining character budget across every selected non-empty chunk; preserved provenance and explicit truncation markers.
- Validation: `tests.test_prompt_rag_security_audit` plus `tests.test_chat_rag` passed (36 tests); RAG/test compilation and `git diff --check` passed. Metadata-only observation on the external stress corpus included all 5/5 selected chunks in 5,698/6,000 characters. No LLM or new dependency was loaded.
- Changed: RAG context builder, two domain-neutral regression tests, RAG knowledge contract, and this progress plan.
- Decision: the external work corpus is temporary test input only. Production retrieval must not contain its brands, company vocabulary, or business-specific capability patterns.
- Legacy note: the already committed retrieval layer contains an earlier CMS/capability lexical bonus from Stage 7B. Stage 7D does not expand it; Stage 8 must measure it explicitly and Stage 10 must remove it when domain-neutral hybrid fusion satisfies the recorded quality gate.
- Checkpoint: `844ac95 fix(rag): distribute context budget across evidence`.
- Next action: stop after the focused commit. On explicit user continuation, begin Stage 8 by adding cross-domain synthetic eval fixtures and recording the current lexical/hashing baseline; do not install an embedding model in Stage 8.

### 2026-08-14 — Stage 8 cross-domain retrieval baseline

- Stage: Stage 8.
- Completed: added a reusable offline eval runner plus 12 synthetic documents across library, observatory, greenhouse, warehouse, museum and microgrid domains; added 10 exact, identifier, paraphrase, typo, conflict and negative cases. The report contains aggregates and case IDs only, uses temporary DB/RAG directories, and does not read user data or load any model.
- Baseline (`local-hash-v1`, `hybrid_v1`, top-5): positive recall@5/MRR/context recall `0.875`; full-hit rate `0.875`; grounded-hit rate `0.5`; paraphrase raw recall `1.0` but grounded-hit `0.0`; typo recall `0.5`; negative rejection `0.5`; expected conflict-status accuracy `0.0`.
- Resource observation: one 10-query run took 68.875 ms total / 6.887 ms mean with 204,043 peak traced bytes. This is a local observation, not a stable performance claim.
- Interpretation: raw top-5 presence overstates quality because hashing collisions can select the expected file while facet diagnostics still report `not_found`. The baseline proves the need for a real semantic provider and later fusion/status calibration; it does not justify tuning against the temporary work corpus.
- Validation: 39 focused eval/prompt-RAG-security/chat tests passed, including deterministic eval results excluding timing and direct CLI output; runner/test compilation, RAG/test compileall and `git diff --check` passed. No LLM, embedding dependency or network access was used.
- Changed: cross-domain fixtures/case manifest, metadata-only eval tool/tests, testing and RAG knowledge docs, active progress record.
- Checkpoint: `3b9fbb7` (`test(rag): add cross-domain retrieval baseline`).
- Next action: completed by the Stage 9 continuation below.

### 2026-08-14 — Stage 9 versioned local embeddings

- Stage: Stage 9.
- Provider decision: selected Ollama `embeddinggemma:latest` as the optional local multilingual semantic adapter, using its native `/api/embed` path and a 256-dimensional versioned generation. Compatibility default remains `local-hash-v1` until the model is explicitly installed and operational reindex controls are added; no model or dependency was downloaded.
- Completed: added provider/model/version/dimension descriptors, strict response validation, bounded batch settings and final `keep_alive=0`; indexing/search now resolve one active generation and never mix stale vectors. Unknown providers, unavailable Ollama and incompatible vectors fail explicitly without hashing fallback.
- Reindex/rollback: a new internal explicit reindex calculates all vectors before an atomic generation replacement, preserves earlier generations, and releases the provider on the last batch. Ordinary ingest cannot silently replace an unchanged corpus after provider switch; search/status report that reindex is required. Returning to the prior generation restores retrieval without editing sources.
- Validation: provider request/shape/no-fallback tests and temporary-corpus generation/reindex/rollback/failure tests added; 56 focused RAG/security/isolation Python tests and 4 Markdown rendering tests passed. Compileall, JavaScript syntax and diff check passed. Warnings are pre-existing datetime/Starlette/resource warnings, not test failures. Live provider smoke skipped because `embeddinggemma` is not installed locally and download was not separately authorized.
- Changed: RAG embedding adapter, settings/example environment, atomic DB generation operations, RAG service integration, focused tests, RAG/testing/changelog docs and this progress record.
- Checkpoint: `feat(rag): add versioned local embeddings` pending commit creation after final validation.
- Next action: stop after the focused commit. On explicit user continuation, begin Stage 10 hybrid lexical/semantic candidate fusion and compare it with the unchanged Stage 8 cross-domain gate; do not run chat models.

### 2026-08-13 — second-device confirmation and Thinking OFF defect

- Stage: Stage 7A completion plus Stage 6 follow-up diagnosis.
- Completed: the user confirmed the second-device UI, profiles/models, streaming response, health endpoint, and missing-token denial behave as specified. Later screenshots show Safari still labels the connection `Not Secure`, so client root-CA trust is not yet complete. Separately inspected the reported latest `Clients RAG test` / `qwen3:4b` exchange without copying its contents into project records.
- Finding: `ollama_think=off` was persisted before the request, but the completed assistant row contained reasoning-style text in `content` and no separate `reasoning`. The installed model template unconditionally opens `<think>` for a new assistant turn. A sequential synthetic control reproduced the defect: `think=false` returned 216 content characters / 0 reasoning characters and exhausted the 80-token cap; `think=true` with `/no_think` returned 0 content / 216 reasoning characters and exhausted the same cap.
- Impact: the UI toggle and settings persistence work, but the current `qwen3:4b` manifest does not provide a reliable non-thinking path; passing native `think=false` turns model reasoning into visible answer content.
- Validation safety: only the already-loaded 4B model was exercised, requests were sequential, and the second request used `keep_alive=0` to unload it.
- Next action: obtain implementation authority for a focused provider/manifest-compatible Thinking OFF fix and regression coverage before Stage 8 cleanup.

### 2026-08-13 — mobile control and RAG relevance diagnosis

- Stage: pre-fix QA for the user-reported mobile chat failure.
- Mobile result: at a real `390x844` viewport, the header Thinking button and the model-picker slider both persisted and cross-synchronized `on`/`off`; the profile was restored to `off`. Sidebar/profile/session navigation, new-chat state, model selector, RAG panel, theme, settings, reasoning dialog, Chat-to-RAG cancellation, composer menu, send enablement, and scroll-to-latest passed with no console warning/error. Voice permission and destructive operations were not invoked against user data.
- Mobile UX finding: primary fixed controls are 44x44 px, while message `Add to RAG` / `Copy` actions are 30 px high and sidebar chat open/delete controls are 34x34 px; these are functional but below the preferred 44 px mobile tap target.
- RAG finding: the source corpus explicitly describes work with WordPress, OpenCart, Joomla, Drupal, MODX, Tilda and custom CMS, including support on any management system. The exact natural-language follow-up selected five unrelated/partial chunks and omitted those direct claims; an explicit CMS-enumeration query retrieved the relevant chunks. This is a retrieval query-expansion/reranking defect, not absence of source evidence.
- Combined failure: with `think=false`, manifest-seeded reasoning entered ordinary `content`, consumed the output budget, ended without a final answer, and was accepted as a completed assistant response. Chat-to-RAG can consequently offer that contaminated content for export because provider reasoning is no longer structurally distinguishable at that point.
- Next action: if implementation is authorized, fix the Qwen hybrid OFF boundary, reject reasoning-only/truncated visible content, improve generic `other CMS` retrieval expansion/reranking, and add automated desktop/mobile two-control regression coverage.

### 2026-08-13 — Stage 7B corrective implementation

- Stage: Stage 7B.
- Completed: hybrid Qwen OFF now omits native `think=false` while retaining transient `/no_think`, so manifest-seeded reasoning remains structural and is suppressed before client/storage. Any token-limit completion fails closed; incomplete worker rows clear partial content/reasoning. RAG query history is deduplicated, direct capability/platform evidence receives a bounded generic lexical bonus, and conflict years are tied to the same exclusive/alternative evidence chunk. Both mobile Thinking surfaces have shared-handler contracts; session and message actions are at least 44 px in the mobile media range.
- Deterministic validation: 163/165 broad Python tests passed; the two failures are the previously recorded ASR baseline (`test_full_analysis_skips_cleaner_by_default_and_sanitizes_speakers`, `test_pipeline_tasks_are_normalized_for_transcript_record`). Eight reasoning/mobile Node tests, context-isolation UI, compileall, JavaScript syntax and diff check passed. The real `Clients RAG test` follow-up now includes direct CMS evidence chunk 197 in top-5 and reports `partial` instead of the prior false `conflict`.
- Live validation: sequential `qwen3:4b` with an artificial 128-token cap produced only structural reasoning and correctly failed with 502; a 512-token OFF request returned final content `готово`, emitted zero reasoning characters through the backend stream, completed with `stop`, and unloaded the model (`loaded_after=[]`).
- Manual status: prior 390x844 control matrix passed before this CSS-only adjustment. The isolated browser could not validate LAN HTTPS because it does not trust the private CA; the user confirms the certificate exists on the phone and will perform the final real-device check. No destructive action, message send, or profile setting change was made in this implementation pass.
- Next action: user checks the updated runtime on the phone; then mark Stage 7B completed, update checkpoint hash, and create the focused commit.

### 2026-08-13 — Stage 7B phone failure and budget correction

- Stage: Stage 7B follow-up.
- Phone evidence: both OFF attempts safely returned `chat_final_answer_incomplete`; no reasoning appeared as content. Screenshots showed `Output tokens=512` while Thinking allowance was 2048 and later 5252. The failure was therefore fail-closed but unusable: OFF policy sent only the 512 output allowance even though this Qwen manifest still performs hidden structural reasoning.
- Correction: hybrid Qwen OFF now receives a single bounded provider cap equal to output + thinking allowances. Non-hybrid OFF remains output-only. The structural reasoning channel is still suppressed before client/storage, and token exhaustion still fails closed.
- Next action: run focused tests and one sequential real-RAG prompt smoke, unload the model, then ask the user to retry after restart.

### 2026-08-14 — Stage 7B phone acceptance and instruct-model follow-up

- Stage: Stage 7B acceptance; Stage 7C intake.
- Accepted evidence: after the compatibility-cap correction and backend restart, the user's real-phone screenshot shows `qwen3:4b` with Thinking OFF returning a direct final answer grounded in RAG, including WordPress, Joomla, OpenCart, MODx, Tilda and Laravel. No reasoning text appears in the chat body and the larger message actions render as intended.
- New observation: user-selected Qwen 2.5 3B/7B Instruct answers appear less complete and inconsistent across generic follow-ups, despite the shared model-independent retrieval path. This is not yet classified as retrieval, prompt assembly or model-grounding behavior.
- Decision: checkpoint all already validated LAN/Thinking/RAG/mobile changes before any further live-model comparison. Stage 7C will run 3B and 7B strictly one at a time and unload between models.
- Next action: inspect final staged diff and create the requested checkpoint; do not start 3B/7B diagnosis until it exists.

## Changed files

### Added

- `docs/progress/security-audit-followup-progress.md`.
- `tests/test_context_isolation.py`.
- `tests/context_isolation_ui.test.mjs`.
- `tests/test_live_llm_security_harness.py`.
- `tests/test_lan_launcher.py`.
- `tools/live_llm_security.py`.

### Modified

- `app/db.py`, session/criteria schemas and routes.
- Chat attachments/routes/service and ASR transcript/pipeline routes.
- Chat prompt policy/service/tasks output boundary and global system policy.
- RAG routes/service and active Web UI request/settings flows.
- Existing focused tests and affected permanent documentation.

### Deleted

- None.

## Validation results

- Static checks: compileall, JS syntax, diff check, and launcher zsh syntax passed. Stage 7D repeated RAG/test compileall and diff check successfully.
- Unit/contract tests: Stage 5 matrix passed; Stage 6 ran 201 broad focused Python tests with only the two baseline ASR failures; all 29 prompt/harness security tests and 28 Node tests passed. Stage 7D passed 36 focused prompt/RAG/chat tests. Stage 8 passed 39 eval/prompt-RAG-security/chat tests. Stage 9 provider/generation tests and focused RAG/security/isolation regression gate passed after the implementation correction recorded above.
- Integration/smoke tests: three installed text models completed 48 final current-code live runs with 0 hard failures after backend enforcement; host LAN HTTPS/API/SSE/CORS/admin/certificate matrix passed.
- Manual/regression checks: user confirmed restored host behavior and functional second-device access; Qwen3 OFF + generic CMS RAG answer passed on the real phone. Safari still displays `Not Secure`, so certificate trust status remains pending separately in Stage 7A.
- Skipped checks and reasons: no vision-capable model image workload was needed because this stage validates OCR/Vision-derived text as an L4 source, not image understanding.
- Remaining uncertainty: model behavioral jailbreak resistance varies; live `embeddinggemma` quality/resources remain unmeasured until a separately authorized install/smoke; hybrid semantic fusion and reranker decision remain Stages 10–11; Safari certificate trust remains unresolved; ambiguous legacy derived rows are quarantined without an automatic promotion/migration.

## Regressions and deferred work

- New regressions: none.
- Pre-existing failures: two ASR tests in focused baseline; prior full-suite plugin DB restore issue.
- Resolved issues: row-based history semantics, profile/session ID substitution, cross-session derived retrieval/deletion, and session-owned object API gaps.
- Unresolved blockers: Stage 7A still requires trusted/secure Safari status. Stage 7B has no remaining blocker; Stage 7C awaits post-checkpoint diagnosis.
- Deferred/technical debt: Tailscale, model router, authenticated multi-user identity, and promotion UX remain separate scope.

## Documentation and permanent records

- Architecture/testing/setup docs: `ARCHITECTURE.md` and `TESTING.md` updated for Stage 5.
- Module knowledge docs: backend/RAG/UI updated; networking now records the private-listener and generated-config contract.
- Changelog/release notes: Unreleased records session isolation and exact history semantics.
- Backlog: remove or refine the now-active live/LAN item only after completion; preserve explicit future Tailscale work.
- Canonical project/task index: security audit follow-up section is the permanent evidence record.

## Checkpoints

- Prior audit checkpoints: `f01424c`, `fead0e5`, `6788daf`, `1a03d3f`, `bd76dc1`, `4d20614`.
- Follow-up checkpoints: `5acb521` (Stage 5), `5faa232` (Stage 6), `553602d` (Stage 7A/7B), `29230f7` and `fe20076` (Stage 7C), `844ac95` (Stage 7D), `3b9fbb7` (Stage 8).

## Continuation state

- Current stage: Stage 10 pending; stop required after the Stage 9 commit until the user explicitly resumes.
- Last completed action: versioned local embedding provider, atomic explicit reindex and previous-generation rollback implemented without changing the active compatibility generation.
- Current repository state: Stage 9 changes only embedding configuration/adapter, generation persistence/service integration, focused tests, affected docs and this progress record. No model was installed or run, and the user's current RAG needs no manual reindex.
- Known risks: live semantic quality/resources are not yet measured; Stage 8 raw recall still overstates grounded quality, and paraphrase diagnostics, typo tolerance, negative rejection and conflict status need improvement. Backend fail-closed output enforcement remains authoritative; Safari still reports `Not Secure`.
- Next exact action: after manual continuation, implement domain-neutral lexical/semantic candidate fusion over version-matched vectors, remove the temporary generic capability bonus only after the cross-domain quality gate passes, then commit and stop.
- Next files: `backend/apps/rag/retrieval.py`, embedding/search integration, Stage 8 eval/tests and affected RAG/testing docs.

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
