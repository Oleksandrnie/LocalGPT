# Security Audit Follow-up Progress

## Task

- Goal: close the residual LocalGPT security risks for profile/session isolation, live Ollama behavior, and real LAN access.
- Problem: the prior Stage 1–4 audit left live-model and LAN validation unverified; the supplemented specification also requires strict chat-session ownership for every derived context path.
- Expected result: backend-enforced isolation, deterministic automated coverage, controlled live-model evidence, and LAN Caddy evidence without public backend binding.
- Source specification: `/Users/oleksandr/Documents/Custom files/Github Repositories/ТЗ для моего обучения/SECURITY_AUDIT_FOLLOWUP_STAGE5_7_v3.md`.
- Branch: `feature/prompt-rag-security-hardening`.
- Started: 2026-08-13.
- Current status: in progress.
- Current stage: Stage 12 completed and ready for its focused checkpoint; Stage 13 has not started.

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
- Status: in_progress.
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
- Status: completed; checkpoint `e60503f` (`feat(rag): fuse lexical and semantic retrieval`).
- Actions: retrieve lexical and semantic candidate pools, normalize and fuse ranks with a domain-neutral method, preserve provenance/diagnostics, diversity and ownership filters, expose rollback to lexical-only retrieval, and remove the earlier CMS/capability-specific lexical bonus once the cross-domain quality gate passes.
- Expected result: cross-domain eval improves without degrading exact identifiers, profile/session isolation, conflicts, or negative queries.
- Validation: Stage 8 eval comparison, isolation/security regressions, bounded latency/memory measurement.
- Completion criterion: predefined cross-domain quality gate passes and no category relies on corpus-specific vocabulary.
- Proposed checkpoint commit: `feat(rag): fuse lexical and semantic retrieval`.

### Stage 11 — Optional universal reranker with resource gates

- Goal: reorder a bounded candidate set by query-evidence relevance when hybrid fusion alone remains insufficient.
- Status: completed; checkpoint `8b43f69` (`test(rag): gate optional reranking by ndcg`); reranker not implemented because no measurable ranking gain is available on the current independent quality gate.
- Actions: decide from Stage 10 metrics whether reranking is justified; if yes, add a small local multilingual reranker over top-N with model/version metadata, time/memory limits, explicit unavailable state, and deterministic adapter tests; if no, mark the stage completed with evidence and no code commit.
- Expected result: top-5 precision improves across unrelated domains without keeping a heavy model resident or invoking the chat LLM.
- Validation: before/after Stage 8 metrics, bounded local smoke, unavailable/timeout tests, sequential resource observation.
- Completion criterion: measurable quality gain exceeds the recorded resource cost; otherwise reranker is rejected rather than added by assumption.
- Proposed checkpoint commit if implemented: `feat(rag): add bounded local reranking`.
- Actual decision checkpoint: `test(rag): gate optional reranking by ndcg`.

### Stage 12 — Reindex lifecycle and operational integration

- Goal: make semantic indexing understandable and safely operable for arbitrary replacement corpora.
- Status: completed; focused checkpoint `feat(rag): expose semantic reindex lifecycle` is the final action of this stage.
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
- Checkpoint: `329abc6` (`feat(rag): add versioned local embeddings`).
- Next action: stop after the focused commit. On explicit user continuation, begin Stage 10 hybrid lexical/semantic candidate fusion and compare it with the unchanged Stage 8 cross-domain gate; do not run chat models.

### 2026-08-14 — Stage 10 interrupted implementation checkpoint

- Stage: Stage 10, `in_progress`; no commit was created because the stage has not completed its regression/documentation gate.
- Goal preserved: replace the single blended score with domain-neutral independent lexical and semantic candidate pools, reciprocal-rank fusion, conservative facet grounding, source diversity and explicit lexical-only rollback. Do not tune against the temporary company corpus and do not run chat models in this stage.
- Implemented so far:
  - removed `CAPABILITY_QUERY_RE`, `PLATFORM_QUERY_RE` and the earlier CMS/platform-support occurrence bonus from production retrieval;
  - introduced `hybrid_v2`, with bounded lexical and semantic pools and normalized reciprocal-rank fusion (`rrf_v1`); candidate diagnostics now expose pool membership and lexical/semantic ranks;
  - semantic-only chunks are no longer discarded merely because lexical overlap is zero;
  - facet diagnostics may use semantic support only above a stricter facet threshold, while semantic candidate admission has its own minimum score;
  - added `lexical_v1` as a non-destructive rollback strategy; stored `hybrid_v1` values migrate in memory to `hybrid_v2`, and `legacy` remains available separately;
  - disabled the semantic pool for `local-hash-v1`, because hashing collisions are not semantic evidence; the current user index therefore remains lexical and does not require reindexing during this stage;
  - expanded generic English stopword handling (`is`) and exclusivity detection (`exclusive*`) so negative rejection and the existing conflict fixture are evaluated correctly without domain vocabulary;
  - extended the eval runner with an explicit strategy selector and actual active embedding generation reporting;
  - added a deterministic cross-domain semantic provider used only by tests. It maps concepts across unrelated library, observatory, warehouse, microgrid, greenhouse and museum fixtures and proves the fusion contract without downloading or loading a model;
  - updated focused tests from `hybrid_v1` to `hybrid_v2` and changed the old CMS regression to assert ordinary lexical-pool evidence rather than a special capability bonus;
  - after the broad regression run exposed a new short-follow-up failure for the phrase `для этого`, expanded the existing deictic-query recognizer from a narrow `это/эта/...` form to `эт\w*`. This last correction is present in the worktree but has not yet been revalidated.
- Measured deterministic quality before the interruption:
  - Stage 8 baseline: positive recall/context `0.875`, grounded hit `0.500`, paraphrase grounded hit `0.000`, typo recall `0.500`, negative rejection `0.500`, conflict status accuracy `0.000`;
  - current `local-hash-v1` with `hybrid_v2`/lexical behavior: positive recall/context `0.875`, grounded hit `0.500`, paraphrase grounded hit `0.000`, typo recall `0.500`, negative rejection `1.000`, conflict status accuracy `1.000`; one observed 10-query run was `8.996 ms/query` and `361,491` traced peak bytes;
  - deterministic semantic `hybrid_v2`: positive recall/context/grounded hit `1.000`, paraphrase grounded hit `1.000`, typo recall `1.000`, negative rejection `1.000`, conflict status accuracy `1.000`;
  - the same semantic fixture generation forced through `lexical_v1`: positive recall/context `0.875`, grounded hit `0.500`, paraphrase grounded hit `0.000`, typo recall `0.500`, negative rejection `1.000`, conflict status accuracy `1.000`;
  - interpretation: improvement comes from the semantic candidate/facet path, not company-specific keywords or the provider identity. These are deterministic contract metrics, not a claim about live EmbeddingGemma quality.
- Validation completed before the final deictic fix:
  - 45 focused tests passed: retrieval eval, prompt/RAG security, Chat RAG and versioned embedding suites;
  - metadata-only CLI reports for default `hybrid_v2` and `lexical_v1` completed;
  - `git diff --check` passed before this progress update;
  - broad 129-test RAG/isolation/pipeline run reported the two known ASR baseline failures plus one new RAG short-follow-up failure. The new failure was diagnosed and corrected in `backend/apps/chat/routes.py`, but the broad suite has not yet been rerun. The two known ASR baselines are `test_full_analysis_skips_cleaner_by_default_and_sanitizes_speakers` and `test_pipeline_tasks_are_normalized_for_transcript_record`.
- Validation still required:
  - rerun the targeted query-composition/RAG test for `для этого`, then the 45-test focused gate;
  - rerun the broad RAG/isolation/pipeline selection and confirm only the two recorded ASR baseline failures remain;
  - run compileall, JavaScript syntax, Markdown rendering and `git diff --check`;
  - inspect default/lexical metadata-only reports and record final resource observations without treating them as stable benchmarks;
  - inspect the entire diff for accidental changes and confirm no production corpus-specific vocabulary or heuristic remains.
- Documentation still required: update `docs/ARCHITECTURE.md`, `docs/knowledge/backend.md`, `docs/knowledge/rag.md`, `docs/TESTING.md`, `docs/CHANGELOG.md` and, if its completed-audit statement is now inaccurate, `docs/security/PROMPT_RAG_SECURITY_AUDIT.md`. Replace claims that default retrieval is `hybrid_v1`/local-hash dense blending or that generic CMS capability gets a special boost. Document `hybrid_v2`, independent pools, RRF, semantic thresholds, `local-hash-v1` lexical behavior, `lexical_v1` rollback and preservation of profile/session ownership filters.
- Changed but uncommitted files: `backend/apps/chat/routes.py`, `backend/apps/rag/retrieval.py`, `backend/apps/rag/service.py`, `tools/rag_retrieval_eval.py`, `tests/test_rag_retrieval_eval.py`, `tests/test_prompt_rag_security_audit.py`, `tests/test_chat_rag.py`, plus this progress file. Do not discard or overwrite these changes.
- Last safe commit: `329abc6` (`feat(rag): add versioned local embeddings`). Stage 10 has no checkpoint yet.
- Expected commit after all gates pass: `feat(rag): fuse lexical and semantic retrieval`.
- Stop rule: after creating that single focused Stage 10 commit, stop and wait for explicit user continuation before Stage 11.

### 2026-08-14 — Stage 10 resumed under read-only test sandbox

- Resumed action: reconciled the worktree with the interrupted checkpoint, re-read mandatory workflow/RAG/backend/provider/testing contracts and reviewed the complete implementation diff. No unrelated file was present.
- Query-composition correction: the initial `эт\w*` fix was found overly broad because it would treat words such as `этикетка` as a reference to prior history. Production regex now enumerates Russian pronoun forms (`это`, `этого`, `этому`, `этой`, etc.) instead of matching every `эт...` word. A paired regression test asserts that `Для этого есть RAG?` keeps the last relevant question while `Что написано на этикетке товара?` does not import unrelated CMS history.
- Read-only functional check: direct `compose_rag_query()` execution passed both sides of that pair. The full unittest version could not start because the current execution sandbox exposes no writable temporary directory; Python `tempfile` rejected `/tmp`, `/var/tmp`, the macOS temp directory and the read-only repository before test setup. A separately created `/tmp/localgpt-stage10.*` directory remained unwritable to the sandboxed Python process, so this is an environment permission blocker rather than a product failure.
- Documentation completed in the worktree: updated `docs/ARCHITECTURE.md`, `docs/knowledge/backend.md`, `docs/knowledge/rag.md`, `docs/TESTING.md`, `docs/CHANGELOG.md` and `docs/security/PROMPT_RAG_SECURITY_AUDIT.md` for `hybrid_v2`, independent pools/RRF, `local-hash-v1` lexical behavior, `lexical_v1` rollback and removal of the CMS/capability bonus.
- Static validation completed in the restricted environment: all 126 Python source files compiled in memory; `node --check web_ui/js/app.js` passed; all 4 Markdown rendering tests passed; `git diff --check` passed; production RAG contains none of `CAPABILITY_QUERY_RE`, `PLATFORM_QUERY_RE`, `support_mentions` or the removed comma-count capability heuristic.
- Current changed files: three production files (`backend/apps/chat/routes.py`, `backend/apps/rag/retrieval.py`, `backend/apps/rag/service.py`), three tests/eval files plus the eval tool, six affected permanent docs and this progress file — 14 tracked files total. All remain unstaged and Stage 10 has no commit.
- Blocking condition: final temporary-DB unittest gates and Git checkpoint require a session with writable temporary storage and workspace/Git metadata. Do not create the Stage 10 commit until those tests run.
- Next exact action after write/temp permission is restored: rerun the two targeted tests, the 46-test focused gate (one new query-composition regression was added), and the 130-test broad selection; accept only the two recorded ASR baseline failures. Then refresh metadata-only metrics, update this record, stage the 14 Stage 10 files, commit once and stop.

### 2026-08-14 — Stage 10 final validation and checkpoint preparation

- Access resolution: writable workspace and temporary storage were restored. A temporary-directory write probe passed, so the prior failure was confirmed as an execution-sandbox permission issue rather than a LocalGPT defect.
- Targeted regression gate: both the recent-history RAG integration test and the paired inflected-reference/`этикетка` false-positive test passed (`2/2`). The production recognizer accepts explicit Russian pronoun forms without using the overbroad `эт\w*` prefix.
- Focused gate: all 46 retrieval-eval, prompt/RAG-security, Chat RAG and versioned-embedding tests passed.
- Broad gate: 130 RAG, Vision RAG, context-isolation, embedding and pipeline-memory tests ran. No Stage 10 regression remained; only the two recorded ASR baseline issues occurred: `test_full_analysis_skips_cleaner_by_default_and_sanitizes_speakers` and `test_pipeline_tasks_are_normalized_for_transcript_record`.
- Final metadata-only quality observation:
  - `local-hash-v1` with `hybrid_v2` remained lexical-only: positive recall/context `0.875`, grounded hit `0.500`, paraphrase grounded hit `0.000`, typo recall `0.500`, negative rejection `1.000`, conflict/status accuracy `1.000`; one 10-query observation was `9.891 ms/query`, `360,634` traced peak bytes;
  - `local-hash-v1` forced through `lexical_v1` produced the same quality matrix, confirming that hashing is not admitted as semantic evidence;
  - deterministic cross-domain semantic `hybrid_v2` reached positive recall/context/grounded hit `1.000`, paraphrase grounded hit `1.000`, typo recall `1.000`, negative rejection `1.000`, conflict/status accuracy `1.000`;
  - the same semantic fixture generation forced through `lexical_v1` returned to positive recall/context `0.875`, grounded hit `0.500`, paraphrase grounded hit `0.000` and typo recall `0.500`, while negative/conflict controls stayed `1.000`;
  - timing/memory values are local observations only, not stable benchmarks. Live EmbeddingGemma threshold/latency/resource validation remains future explicit work.
- Static validation: `compileall` for `app`, `backend` and `tests`, JavaScript syntax, all four Markdown-rendering tests and `git diff --check` passed.
- Final scope inspection: 14 tracked Stage 10 files changed; no unrelated file or user runtime data changed. Production retrieval contains no CMS/company/brand vocabulary, `CAPABILITY_QUERY_RE`, `PLATFORM_QUERY_RE`, support-density/comma-count bonus or provider-identity quality shortcut. No chat model was run or downloaded and no user RAG was reindexed.
- Documentation: affected architecture, backend, RAG, testing, changelog and security-audit records now describe `hybrid_v2`, independent pools, `rrf_v1`, conservative semantic/facet thresholds, `local-hash-v1` lexical-only behavior and `lexical_v1` rollback.
- Decision: Stage 10 quality and safety gates pass. Create exactly one focused commit `feat(rag): fuse lexical and semantic retrieval`, then stop before Stage 11. Record its hash at the next resumed checkpoint without amending this completed stage.

### 2026-08-14 — Stage 11 reranker quality-gate analysis

- Stage 10 checkpoint reconciled: HEAD is `e60503f` (`feat(rag): fuse lexical and semantic retrieval`) on `feature/prompt-rag-security-hardening`; the working tree was clean at Stage 11 start.
- Scope lock: Stage 11 may add only a reproducible metadata-only ranking metric and an evidence-backed reranker decision. It must not download/load a reranker or chat model, touch the user corpus, tune thresholds against the temporary company RAG, start reindex UI work, or change retrieval behavior without a demonstrated cross-domain gap.
- Measurable gate: a reranker is eligible only if the unchanged cross-domain fixture shows non-ideal ordering after `hybrid_v2` while recall, grounded facet coverage, exact identifiers, negative rejection, conflict accuracy and profile/session isolation remain non-regressed. Ranking order is measured with binary relevance `nDCG@k`; for each case, all explicitly expected sources should occupy the first `expected_source_count` positions. Any candidate must then show a material nDCG/top-N gain with bounded latency/memory, explicit unavailable/timeout state and no persistent heavy model residency.
- Initial metadata-only observation using the Stage 10 deterministic semantic provider: every single-source positive case placed its expected source at rank 1; the two-source conflict case placed both expected sources at ranks 1–2; all eight positive cases therefore reached `nDCG@5=1.000`. Both negative cases remained empty and conflict status matched. No raw query/corpus content was persisted.
- Preliminary decision: the available labeled fixture is saturated, so a reranker cannot demonstrate additional ranking quality and is not eligible for implementation or download in this stage. Add `nDCG@k` to the canonical eval report and regression tests, rerun the Stage 10 comparison, then record the final defer/reject decision. A future reranker reconsideration requires a larger domain-independent judged set or real-provider evidence that exposes a non-ideal top-N ordering.
- Expected tracked files: `tools/rag_retrieval_eval.py`, `tests/test_rag_retrieval_eval.py`, affected RAG/testing/changelog documentation and this progress file. No production retrieval file is expected to change.
- Proposed checkpoint: `test(rag): gate optional reranking by ndcg`.
- Implemented evaluation change: the metadata-only report now records per-case binary-relevance `ndcg_at_k` and `ideal_ranked_hit`, plus aggregate `ndcg_at_k` and `ideal_ranked_hit_rate`. The report schema remains metadata-only and contains no raw query/content.
- Final comparison on the unchanged fixture:
  - deterministic semantic `hybrid_v2`: positive recall/context/grounded/MRR/nDCG/ideal-ranked-hit `1.000`; paraphrase and typo grounded/nDCG `1.000`; negative rejection and conflict/status accuracy `1.000`;
  - the same semantic fixture generation through `lexical_v1`: positive recall/MRR/nDCG/ideal-ranked-hit `0.875`, grounded `0.500`; typo recall/nDCG/grounded `0.500`; paraphrase grounded `0.000`; controls remain `1.000`;
  - current `local-hash-v1` remains lexical-only and matches the `0.875` positive ranking ceiling. Timing/memory observations are local only and were not used to tune production thresholds.
- Validation: all 47 focused retrieval-eval, prompt/RAG-security, Chat RAG and embedding tests passed; compileall for `app`, `backend`, `tests` and `tools`, JavaScript syntax, all four Markdown-rendering tests and `git diff --check` passed.
- Final decision: do not add or download a reranker now. The semantic fusion already puts every judged relevant source in the ideal prefix, so any claimed gain would be unmeasurable and the additional model/dependency/latency/memory would violate the resource gate. Reconsider only after a larger domain-independent judged set or live-provider evidence produces `ndcg_at_k < 1`/non-ideal top-N. This is a deferred eligibility condition, not a hidden fallback and not tuning against the temporary work corpus.
- Changed files: eval tool, focused eval tests, `docs/TESTING.md`, `docs/knowledge/rag.md`, `docs/CHANGELOG.md` and this progress file. Production retrieval, runtime configuration and user data are unchanged; no model or reindex operation ran.

### 2026-08-14 — Stage 12 operational lifecycle analysis

- Stage 11 checkpoint reconciled: HEAD is `8b43f69` (`test(rag): gate optional reranking by ndcg`) on `feature/prompt-rag-security-hardening`; the working tree was clean at Stage 12 start.
- Confirmed backend state: `reindex_embeddings()` already computes the complete selected generation before `replace_embedding_generation()` publishes it, and previous generations remain for rollback. There is no HTTP endpoint/task lifecycle for that operation. `GET /rag/status` reports only `ready`/`reindex_required`, uses retrieval-scoped chunk counts, and cannot distinguish changed/unindexed source files, configuration failure, active progress or the last safe failure.
- Confirmed UI state: the RAG modal has upload, ingest and refresh only. The visible `Индексировать` action calls ordinary ingest; there is no explicit semantic-generation reindex action, configured provider/model summary, progress recovery or actionable error state. Stale JavaScript references to absent force/copy controls are not part of the visible UI and will be removed only where touched by this stage.
- Acceptance criteria:
  - status distinguishes `ready`, `ingest_required`, `reindex_required` and safe configuration failure, reports configured descriptor plus profile-wide total/indexed/missing chunks and available generation counts without filesystem/runtime addresses;
  - upload/replacement is visible as `ingest_required`; deletion removes its chunks/embeddings; provider switching never mixes generations;
  - explicit `POST /rag/reindex` starts at most one process-local background operation globally, returns immediately, exposes profile-owned progress through status/task lookup and never runs automatically;
  - provider/config/source-change failures publish stable public error codes without raw provider exceptions or partial generation replacement;
  - generation publication validates the full current profile chunk set in the same DB transaction, so a concurrent source change fails closed and preserves the prior generation;
  - UI shows the generation state and progress, confirms the potentially expensive action, restores polling after refresh and remains usable on desktop/mobile in both themes.
- Scope boundaries: no user-corpus reindex, model download, chat/embedding live smoke, new reranker, Stage 13 model run or corpus-specific rule. Process-local task history may reset on backend restart; canonical generation state is always reconstructed from SQLite/source metadata.
- Planned files: RAG task/service/routes/schema and DB repository, active RAG HTML/JS/CSS, focused Python/Node tests, affected architecture/backend/RAG/UI/testing/changelog docs and this progress record.
- Validation plan: existing embedding baseline; new lifecycle success/failure/concurrency/source-change tests; RAG/security/isolation regression selection; Node UI contract; syntax/compile/diff checks; isolated desktop/mobile light/dark read-only UI inspection. Expected checkpoint: `feat(rag): expose semantic reindex lifecycle`.

### 2026-08-14 — Stage 12 implementation and validation

- Backend lifecycle: `GET /rag/status` now reports configured descriptor, profile-wide total/indexed/missing chunks, pending sources, available generations and one of `ready`, `ingest_required`, `reindex_required` or `configuration_error`. Configuration/provider failures are reduced to stable public codes; absolute paths and raw exception text are not returned.
- Explicit operation: `POST /rag/reindex` starts one process-local background task globally and returns immediately; profile-owned `GET /rag/reindex/{task_id}` exposes queued/running/completed/failed progress. A second profile cannot read the task, and any concurrent reindex is rejected. No model download, automatic reindex or user-corpus mutation was added.
- Atomicity: generation publication compares the complete current profile chunk set inside the same SQLite transaction. Duplicate, missing or newly added chunks cause `rag_embedding_source_changed`; the prior generation remains unchanged. Old generations remain listed for explicit configuration rollback.
- Restart contract: task progress is intentionally process-local. While the backend is alive, `/rag/status` exposes the latest operation and UI resumes polling after refresh/reopen. After restart, a missing task is treated as a warning and canonical generation readiness is recomputed from SQLite plus source metadata.
- UI: the RAG modal shows configured provider/model/version, indexed totals, pending sources, safe failure text and progress. Semantic reindex is enabled only for `reindex_required`, requires confirmation with model/chunk count and local-load warning, and temporarily disables competing source operations.
- Automated validation: all 11 embedding/provider/lifecycle tests passed; the broader prompt/RAG-security, Chat RAG, Vision RAG, context-isolation and retrieval-eval selection passed all 54 tests. JavaScript syntax, `git diff --check`, four Markdown rendering tests and three new RAG reindex UI contract tests passed.
- Manual UI validation: an isolated temporary DB/source directory was served without loading any model. Desktop and 390×844 mobile views passed in dark and light themes; generation card, disabled unavailable reindex action, responsive scrolling and keyboard focus were visible and usable, with zero browser console errors. The isolated server and temporary data were removed afterwards.
- Changed files: DB generation repository; RAG schema/routes/service and new process-local task registry; RAG HTML/JS/CSS; focused Python/Node tests; architecture/backend/RAG/UI/testing/changelog records; this progress file.
- Scope confirmation: no CMS/company/brand/corpus-specific rule, reranker, model download, chat LLM call, embedding live smoke or user RAG reindex was introduced. Stage 13 remains pending explicit user continuation.

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
- Stage 12: `backend/apps/rag/reindex_tasks.py`, `tests/rag_reindex_ui.test.mjs`.

### Modified

- `app/db.py`, session/criteria schemas and routes.
- Chat attachments/routes/service and ASR transcript/pipeline routes.
- Chat prompt policy/service/tasks output boundary and global system policy.
- RAG routes/service and active Web UI request/settings flows.
- Existing focused tests and affected permanent documentation.
- Stage 12: embedding generation repository, RAG lifecycle schema/routes/service, RAG modal HTML/JS/CSS, focused lifecycle tests and affected architecture/backend/RAG/UI/testing/changelog records.

### Deleted

- None.

## Validation results

- Static checks: compileall, JS syntax, diff check, and launcher zsh syntax passed. Stage 7D repeated RAG/test compileall and diff check successfully. Stage 12 final gate passed compileall for app/backend/tests/tools, JavaScript syntax, `git diff --check`, four Markdown-rendering tests and three RAG lifecycle UI contracts.
- Unit/contract tests: Stage 5 matrix passed; Stage 6 ran 201 broad focused Python tests with only the two baseline ASR failures; all 29 prompt/harness security tests and 28 Node tests passed. Stage 7D passed 36 focused prompt/RAG/chat tests. Stage 8 passed 39 eval/prompt-RAG-security/chat tests. Stage 9 provider/generation tests and focused RAG/security/isolation regression gate passed after the implementation correction recorded above. Stage 12 passed 11 embedding/provider/lifecycle tests plus 54 broader RAG/security/isolation/eval tests.
- Integration/smoke tests: three installed text models completed 48 final current-code live runs with 0 hard failures after backend enforcement; host LAN HTTPS/API/SSE/CORS/admin/certificate matrix passed.
- Manual/regression checks: user confirmed restored host behavior and functional second-device access; Qwen3 OFF + generic CMS RAG answer passed on the real phone. Stage 12 RAG generation UI passed isolated desktop/mobile dark/light inspection and keyboard-focus/console checks without touching user data. Safari still displays `Not Secure`, so certificate trust status remains pending separately in Stage 7A.
- Skipped checks and reasons: no vision-capable model image workload was needed because this stage validates OCR/Vision-derived text as an L4 source, not image understanding.
- Remaining uncertainty: model behavioral jailbreak resistance varies; live `embeddinggemma` quality/resources remain unmeasured until separately authorized Stage 13 work; process-local reindex progress does not survive a backend restart, although canonical generation state does; Safari certificate trust remains unresolved; ambiguous legacy derived rows are quarantined without an automatic promotion/migration.

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
- Follow-up checkpoints: `5acb521` (Stage 5), `5faa232` (Stage 6), `553602d` (Stage 7A/7B), `29230f7` and `fe20076` (Stage 7C), `844ac95` (Stage 7D), `3b9fbb7` (Stage 8), `329abc6` (Stage 9), `e60503f` (Stage 10), `8b43f69` (Stage 11). Stage 12 hash is recorded after its focused checkpoint.

## Continuation state

- Current stage: Stage 12 `completed`; backend lifecycle, safe operational API, responsive UI, automated coverage, isolated manual QA and affected documentation are complete. Stage 13 has not started.
- Last completed action: passed isolated desktop/mobile light/dark QA with no browser console errors, removed the temporary runtime, and updated permanent/progress documentation.
- Current repository state before checkpoint: only Stage 12 implementation, tests and affected records are modified/untracked. User data and model state are unchanged; no model was installed, downloaded or run and no user RAG was reindexed.
- Known risks: background task history is process-local, so an in-flight operation cannot resume across backend restart; canonical SQLite/source state does recover and the UI explains this. Live EmbeddingGemma score distribution, thresholds, latency and memory remain unmeasured until Stage 13 authorization. Backend output enforcement, profile/session ownership and sequential model loading remain authoritative. Safari still reports `Not Secure` separately.
- Next exact action in this turn: inspect and stage only the Stage 12 files, commit `feat(rag): expose semantic reindex lifecycle`, verify clean status and stop.
- Next action after explicit user continuation: record the Stage 12 checkpoint hash, then begin only Stage 13 sequential validation. Run 3B, 7B and 4B strictly one at a time with unload verification; do not tune retrieval against the temporary work corpus.

### Continuation prompt for Stage 13

```text
Продолжи LocalGPT строго со Stage 13 по активному progress-файлу
docs/progress/security-audit-followup-progress.md и skill project-progress-workflow.

Репозиторий:
/Users/oleksandr/Documents/Custom files/Github Repositories/LocalGPT

Ветка:
feature/prompt-rag-security-hardening

Сначала проверь clean status и фактический HEAD. Запиши hash завершённого Stage 12 commit
`feat(rag): expose semantic reindex lifecycle` в progress-файл. Не начинай Stage 12 заново.

Stage 12 contract:
- status различает ready / ingest_required / reindex_required / configuration_error;
- semantic reindex запускается только явно и допускает одну process-local operation глобально;
- task lookup profile-owned, raw paths/errors не раскрываются;
- публикация generation атомарно отклоняется, если source chunks изменились;
- UI подтверждает нагрузку, показывает progress/error и восстанавливает canonical state после restart.

Выполни только Stage 13: последовательную валидацию общего retrieval/model grounding.
- Сначала запусти cross-domain metadata-only deterministic suite и зафиксируй retrieval metrics отдельно от generation quality.
- Любая необходимая переиндексация пользовательского corpus запускается только после явного согласования с пользователем; пользователь ранее предложил выполнять её сам через UI.
- Прогоняй `qwen2.5:3b-instruct`, затем `qwen2.5:7b-instruct`, затем `qwen3:4b` строго по одному.
- Перед следующим model run докажи, что предыдущая модель выгружена; финальный вызов каждой модели должен освобождать Ollama resource.
- Не скачивай модели, не запускай их параллельно и не меняй thresholds/эвристики по временному рабочему RAG.
- Отдельно запиши: одинаковые retrieved chunk IDs/diagnostics, полноту ответа модели, unsupported claims, Thinking boundary и resource observation.
- Если configured semantic generation ещё не создан, не обходи Stage 12 contract silent fallback; остановись на точном operational prerequisite и попроси пользователя выполнить подтверждённое действие через UI.
- Обнови progress и только затронутые permanent records, создай один focused Stage 13 commit и остановись.
```

### Completed Stage 12 continuation prompt (historical)

```text
Продолжи LocalGPT строго со Stage 12 по активному progress-файлу
docs/progress/security-audit-followup-progress.md и skill project-progress-workflow.

Репозиторий:
/Users/oleksandr/Documents/Custom files/Github Repositories/LocalGPT

Ветка:
feature/prompt-rag-security-hardening

Сначала проверь clean status и фактический HEAD. Запиши hash завершённого Stage 11 commit
`test(rag): gate optional reranking by ndcg` в progress-файл.

Stage 11 decision:
- optional reranker не реализован и не скачан;
- deterministic semantic hybrid_v2 уже имеет positive nDCG/ideal-ranked-hit 1.0,
  perfect paraphrase/typo grounding и perfect negative/conflict controls;
- reranker можно пересмотреть только при новой domain-independent judged выборке или
  live-provider evidence с неидеальным top-N, не по временному пользовательскому corpus.

Выполни только Stage 12: безопасный operational lifecycle semantic reindex.
- Сначала исследуй существующие RAG status/reindex APIs, settings UI и atomic generation lifecycle.
- Должны быть понятны current configured generation, indexed/ready/stale/reindex-required/failed state,
  progress/error metadata и безопасный explicit запуск; никакого silent reindex/download.
- Replacement/delete должен инвалидировать правильное generation, rollback не должен смешивать vectors.
- Сохрани profile/session isolation, local-only provider behavior и отсутствие raw paths/errors.
- UI-проверки нужны для desktop/mobile и обеих тем только если Stage 12 меняет UI.
- Не запускай chat LLM; embedding smoke/reindex пользовательского corpus только по отдельному разрешению.
- Обнови progress и затронутые permanent docs, создай один focused Stage 12 commit и остановись.
```

### Completed Stage 11 continuation prompt (historical)

```text
Продолжи LocalGPT строго со Stage 11 по активному progress-файлу
docs/progress/security-audit-followup-progress.md и skill project-progress-workflow.

Репозиторий:
/Users/oleksandr/Documents/Custom files/Github Repositories/LocalGPT

Ветка:
feature/prompt-rag-security-hardening

Сначала проверь clean status и фактический HEAD. Запиши hash завершённого Stage 10 commit
`feat(rag): fuse lexical and semantic retrieval` в progress-файл. Не начинай Stage 10 заново.

Ограничения:
- выполнить только Stage 11, затем отдельный checkpoint при наличии tracked changes и стоп;
- не запускать chat LLM, не скачивать модели и не переиндексировать пользовательский RAG;
- не добавлять CMS/company/brand vocabulary или эвристики под временный corpus;
- не менять Stage 10 thresholds по рабочему RAG и не возвращать capability bonus;
- не переходить к Stage 12 reindex UI или Stage 13 live-model validation.

Stage 10 evidence:
- deterministic semantic hybrid_v2 достиг 1.0 для positive grounded/paraphrase/typo,
  negative rejection и conflict/status accuracy;
- та же fixture generation через lexical_v1 вернулась к 0.5 grounded,
  0.0 paraphrase grounded и 0.5 typo recall;
- local-hash-v1 остаётся lexical-only;
- 46 focused tests passed; broad 130-test gate содержит только две известные ASR baseline issues;
- production code не содержит CMS/company/brand/capability bonus.

Порядок Stage 11:
1. Сформулируй измеримый reranker quality gate поверх cross-domain fixture: top-N relevance,
   отсутствие регрессий exact identifiers, negatives, conflicts, profile/session isolation,
   bounded latency/memory и explicit unavailable state.
2. Сверь gate с уже достигнутыми Stage 10 метриками. Если разметка уже насыщена и нельзя
   доказать дополнительную пользу, не добавляй модель/dependency: зафиксируй evidence-backed
   решение отложить или отклонить reranker.
3. Если остаётся измеримый gap, сначала исследуй минимальный локальный multilingual reranker,
   его лицензию, размер и runtime contract. Не скачивай его без отдельного разрешения пользователя.
4. Обнови progress и только фактически затронутые permanent docs. Создай один focused commit
   только если Stage 11 меняет tracked files, затем остановись.
```

### Completed Stage 10 continuation prompt (historical)

```text
Продолжи LocalGPT строго с незавершённого Stage 10 по активному progress-файлу
docs/progress/security-audit-followup-progress.md и skill project-progress-workflow.

Репозиторий:
/Users/oleksandr/Documents/Custom files/Github Repositories/LocalGPT

Ветка:
feature/prompt-rag-security-hardening

Последний безопасный commit:
329abc6 feat(rag): add versioned local embeddings

Важно:
- не начинай Stage 10 заново и не откатывай незакоммиченные изменения;
- сначала прочитай AGENTS.md, skill полностью, обязательные RAG/backend/provider/testing docs и секцию
  «2026-08-14 — Stage 10 interrupted implementation checkpoint» в progress-файле;
- проверь `git status` и полный diff: ожидаются изменения Stage 10 в
  backend/apps/chat/routes.py,
  backend/apps/rag/retrieval.py,
  backend/apps/rag/service.py,
  tools/rag_retrieval_eval.py,
  tests/test_rag_retrieval_eval.py,
  tests/test_prompt_rag_security_audit.py,
  tests/test_chat_rag.py,
  docs/progress/security-audit-followup-progress.md;
- никакие chat LLM не запускать, модели не скачивать и пользовательский RAG не переиндексировать;
- не добавлять названия CMS, компаний, брендов или эвристики под временный рабочий corpus;
- Stage 10 должен завершить универсальные независимые lexical/semantic candidate pools,
  domain-neutral reciprocal-rank fusion, provenance/diagnostics, source diversity,
  profile/session isolation и lexical_v1 rollback;
- local-hash-v1 не считать semantic evidence: на нём semantic pool должен оставаться выключенным;
- старый CMS/capability bonus уже удалён и возвращать его нельзя;
- не переходить к reranker/Stage 11, UI reindex/Stage 12 или live chat-model tests/Stage 13.

Первая команда проверки:
venv/bin/python -m unittest \
  tests.test_pipeline_memory.LocalGPTPipelineMemoryTestCase.test_rag_search_uses_recent_user_history_for_short_followup \
  tests.test_prompt_rag_security_audit.PromptRagSecurityAuditTestCase.test_rag_query_composition_keeps_latest_history_for_short_deictic_followup -v

Она проверяет последнюю незапущенную коррекцию: RAG_REFERENTIAL_QUERY_RE теперь принимает
склонённое «этого» через `эт\\w*`. Если тест не проходит, диагностируй причину без corpus-specific правил.

После этого:
1. Запусти focused gate:
   venv/bin/python -m unittest \
     tests.test_rag_retrieval_eval \
     tests.test_prompt_rag_security_audit \
     tests.test_chat_rag \
     tests.test_rag_embeddings -q
2. Запусти broad gate:
   venv/bin/python -m unittest \
     tests.test_rag_retrieval_eval \
     tests.test_prompt_rag_security_audit \
     tests.test_chat_rag \
     tests.test_vision_rag \
     tests.test_context_isolation \
     tests.test_rag_embeddings \
     tests.test_pipeline_memory -q
   Допустимы только два уже зафиксированных ASR baseline failure:
   - test_full_analysis_skips_cleaner_by_default_and_sanitizes_speakers
   - test_pipeline_tasks_are_normalized_for_transcript_record
   Любая другая ошибка — новая regression и должна быть исправлена до commit.
3. Повтори metadata-only eval для `hybrid_v2` и `lexical_v1`; не сохраняй raw corpus/query
   в проект и не объявляй timing стабильным benchmark.
4. Выполни compileall, `node --check web_ui/js/app.js`,
   `node tests/markdown_rendering.test.mjs` и `git diff --check`.
5. Обнови только затронутые постоянные документы: ARCHITECTURE, backend, RAG, TESTING,
   CHANGELOG и при необходимости security audit. Удали устаревшие утверждения про default
   hybrid_v1, local-hash dense semantic behavior и специальный CMS capability bonus.
6. Обнови progress-файл финальными метриками, validation и changed files.
7. Проверь полный staged diff, создай ровно один focused commit:
   feat(rag): fuse lexical and semantic retrieval
8. Проверь `git status`, запиши hash checkpoint и остановись. Не начинай Stage 11,
   пока пользователь явно не напишет продолжение.
```

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
