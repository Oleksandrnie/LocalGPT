# Open Source Readiness Audit Progress

## Task

- Goal: Audit LocalGPT for public source-code readiness, verify findings against the implementation and available Git history, apply safe security/documentation/CI improvements, and prepare a release checklist and readiness report.
- Problem: The repository currently has no CI workflow or transitive dependency lock, and history/code review found credential/user-data exposure plus unbounded upload and remote-access concerns.
- Expected result: A reviewed report with architecture, P0–P3 risk register, security and supply-chain evidence, verified tests/setup limits, owner decisions, release checklist and verdict. No publication, push, visibility change, history rewrite, license choice or model download.
- Source specification: User-provided “ТЗ №1. LocalGPT — Open Source Readiness, Security & Distribution Audit”.
- Branch: `codex/opensource-readiness-audit` (created from clean `dev` at `e73a938`).
- Selected model and effort for this stage (execution metadata; routing policy is in applicable `AGENTS.md`): GPT-6.1 Sol / Medium for architecture, security implementation and backend work; GPT-6 Sol / High-xHigh for bounded audit analysis as specified by repository routing.
- Effective executor metadata: unavailable.
- Started: 2026-10-21.
- Current status: in progress.
- Current stage: readiness report, documentation and quality gates.

## Instructions and precedence

- Direct user requirements: Create a feature branch and execute the audit/TЗ; full implementation authority for the task; final work summary.
- Task-specific requirements: Do not publish or change repository visibility; do not destructively rewrite history; do not remove licensing/activation controls; audit only implemented features; do not add real private data to tests/docs.
- Discovered AGENT.md/AGENTS.md files and applicable rules: Root `AGENTS.md` only. Read before analysis. Use staged progress/checkpoints, focused tests, no heavy model runs, preserve unrelated work, update only affected permanent docs, no push.
- Conflicts and resolutions: `AGENTS.md` requires adding the task progress file with `git add -f` and updating it in checkpoints; the generic project-progress skill says progress remains local-only. Repository-specific `AGENTS.md` has precedence, so this file will be included in focused local checkpoints. A separate tracked `temporary/multimodal-audit-progress.md` is pre-existing and remains untouched; this task uses a separate record on its explicitly requested branch.
- Git authorization: User explicitly requested a new branch. The selected progress workflow authorizes focused local stage commits. No push or remote GitHub mutation is authorized.
- Local-only progress state: `temporary/` is ignored, but the repository contract requires force-adding this task's file at checkpoints.

## Scope lock

### In scope

- Verify actual launcher/backend/UI/provider/storage flows and platform support.
- Review local storage/privacy, network boundary, API authorization, uploads, subprocesses/plugins, dependency and model provenance, licensing, Git history and CI/release posture.
- Run proportionate deterministic tests/smoke checks without loading or downloading models.
- Fix bounded security defects with regression coverage; update README and only the affected architecture/testing/dependency/security/changelog records.
- Prepare a release checklist and a technical/security readiness report with unresolved owner decisions.

### Out of scope

- Publishing, pushing, changing GitHub visibility/About/topics/releases, or sending external messages.
- Rewriting or deleting shared Git history; selecting the project's open-source license; changing licensing/business/activation policy.
- Loading/downloading large AI models, live ASR/LLM/TTS workloads, or claiming unverified platform support.
- Broad refactors or adding features absent from the project.

### Affected areas and expected files

- `backend/apps/model_transfer/`, ASR/OCR/criteria upload boundaries and targeted tests if fixes are confirmed.
- Launcher/network default and corresponding tests/docs if security review confirms a safe-compatible change.
- `README.md`, `docs/ARCHITECTURE.md`, `docs/DEPENDENCIES.md`, `docs/TESTING.md`, `docs/CHANGELOG.md`, `docs/README.md` as factually needed.
- One audit/readiness report under `docs/security/`; CI quality workflow under `.github/workflows/` if locally validated.
- `License` is not modified pending explicit owner licensing/contact decision.

### Dependencies and compatibility

- Active app: `backend.server:app`, static UI `web_ui/gui_html.html` / `web_ui/js/app.js`, SQLite shared storage, provider apps under `backend/apps/`.
- Canonical Python dependencies: `app/requirements.txt`; no tracked transitive lock or `.github` workflow currently found.
- Model weights and runtime user data are intended to remain local and are not installation defaults.

### Risks and rollback concerns

- Historical credential-like values and SQLite chat records were found in reachable Git history; current validity/content was not emitted. Do not push this branch. Treat potentially live values as exposed. Remediation requires private owner review, rotation as applicable and an approved history rewrite before any public publication.
- LAN mode and several management endpoints lack global authentication; any network/security behavior change can affect the existing private-access workflow.
- Direct Piper dependency is GPL-3.0-or-later while root `License` says All Rights Reserved; owner must decide project licensing/provenance and distribution compatibility.
- Large/unbounded uploads and ZIP expansion can consume disk/memory; tests must use synthetic temporary files only.

## Baseline

- Current behavior: LocalGPT is a static UI + FastAPI runtime with local SQLite/models, Ollama chat/vision, whisper.cpp/faster-whisper ASR, Piper TTS, Tesseract OCR, RAG, metadata-only plugins, model transfer and optional private network access. macOS no-argument launcher starts Caddy on a private LAN IP by default; backend has no global caller authentication. README and subsystem docs exist; CI workflow and release material do not.
- Existing tests: broad `unittest` and Node suites documented in `docs/TESTING.md`; docs already record three known full-suite failures.
- Validation commands: `git diff --check`; `venv/bin/python -m compileall -q app backend tests`; `node --check web_ui/js/app.js`; `node tests/markdown_rendering.test.mjs`; `node --test tests/*.test.mjs`; full isolated `unittest discover` with `RAG_EMBEDDING_PROVIDER=local_hash` and temporary DB.
- Validation scope: full-project audit; deterministic tests by affected subsystem, full suite where safe, isolated local health/UI smoke, and no live-model generation.
- Scope decision and reason: Cross-cutting security and release-readiness review spans shared API, multiple feature uploads, install/security docs and Git history.
- Pre-existing failures: Baseline full suite ran 424 tests: 421 passed; 3 failed (two ASR pipeline fixture/contract mismatches: `test_full_analysis_skips_cleaner_by_default_and_sanitizes_speakers`, `test_pipeline_tasks_are_normalized_for_transcript_record`; one plugin-doc test had missing SQLite table `app_settings`). `docs/BACKLOG.md` had already documented the ASR and plugin-suite issues. Node full suite passed 51/51; static baseline and Markdown rendering passed.
- Branch and working-tree state: `codex/opensource-readiness-audit`, clean at start, based on `e73a938`.
- Unrelated user changes to preserve: Existing `temporary/multimodal-audit-progress.md` and all inherited project content.
- Temporary files intentionally excluded from commits: synthetic upload/ZIP fixtures and runtime smoke database/output files under OS temporary directories.

## Architecture

- Current flow: Setup/launcher → `run_localgpt.py` → Uvicorn `backend.server:app` → shared `app/` and feature routers in `backend/apps/` → local Ollama/ASR/TTS/OCR binaries/providers and optional external catalog/download APIs → SQLite and project-scoped runtime storage → static browser UI.
- Target flow: No feature architecture change planned. Readiness work will document verified trust/data boundaries and add bounded validation/cleanup at existing HTTP file/archive boundaries.
- Contracts and boundaries: routers validate HTTP inputs and delegate to feature service; models and user content remain in configured local paths; arbitrary plugin code is not executed; LAN proxy reaches localhost backend; profile/session IDs currently provide data ownership, not caller authentication.
- Data and ownership: User chat/history/documents/transcripts/attachments/RAG/model files are local by default and ignored by current Git rules; configured remote OpenAI-compatible endpoints and explicit model/catalog/install flows can send requests/downloads outside the device.

## Implementation stages

### Stage 1 — Security boundary fixes

- Goal: Close confirmed upload/resource exhaustion issues without changing model behavior.
- Status: complete
- Actions: Cap model-transfer archive upload and manifest/member expansion before allocation; enforce upload limits for ASR/OCR/criteria; ensure temporary inputs are cleaned on validation/error paths; add synthetic regression coverage; upgrade vulnerable pinned dependencies.
- Expected result: Bounded bytes and cleanup on every reject/failure branch; dependency versions install on the documented minimum Python.
- Validation: Targeted model-transfer, ASR/OCR/criteria upload and launcher tests: 36/36 passed; `git diff --check`, Python compile, POSIX `sh -n`, `pip check`; isolated `pip-audit -r app/requirements.txt`: no known vulnerabilities found after upgrades.
- Completion criterion: Oversize and malformed inputs fail with bounded errors and leave no artifacts; valid-path tests remain green.
- Affected files: `app/services/upload_limits.py`, `app/routes/criteria.py`, `backend/apps/{asr,ocr,model_transfer}/`, `app/requirements.txt`, Python minimum-version launchers/setup/docs, `tests/test_upload_boundaries.py`, setup contract tests.
- Dependencies: Stage 0 audit evidence.
- Checkpoint commit: `710ec83 fix(security): bound uploads and archive processing`.

### Stage 2 — Secure default networking and API posture

- Goal: Align the default startup path with localhost-only trust; make LAN exposure an explicit, clearly documented opt-in or record any behavior that requires an owner decision.
- Status: complete
- Actions: Verify all entry points and existing launcher tests; make ordinary startup local-only; stop a previously managed Caddy LAN listener on macOS when returning to ordinary startup; retain explicit LAN start/stop commands; document the absence of per-client auth for explicit private-network access and privileged route boundaries.
- Expected result: Ordinary startup does not silently expose user data to other devices; optional network access remains explicit and its limits are clear.
- Validation: `tests.test_lan_launcher` + setup contract tests 20/20 passed; POSIX and zsh syntax checks passed. No real LAN/Tailscale listener changes in this environment.
- Completion criterion: Default path and documented LAN/Tailscale controls agree with code; no public bind/Funnel behavior added.
- Affected files: ordinary/explicit LAN launchers, `tools/LTrnsrb.sh`, stop entry points, launcher tests, README/network/testing docs.
- Dependencies: Stage 0 audit evidence.
- Checkpoint commit: `fix(security): make LAN access explicit` (to be created after staged-diff review).

### Stage 3 — Readiness report, documentation and quality gates

- Goal: Publish accurate local documentation and prepare repeatable PR/release checks.
- Status: pending
- Actions: Record architecture, risk register, dependency/license/history findings, supported-vs-unverified setup matrix, existing module tests/limitations, release checklist, draft GitHub About/topics/release text, and CI gates with least privilege.
- Expected result: README points to a complete report/checklist; no unsupported offline/privacy/platform/license claims.
- Validation: Markdown rendering, workflow YAML/config checks, dependency/secret scan as available, docs links and `git diff --check`.
- Completion criterion: Every TЗ deliverable is either evidenced, explicitly blocked on owner decision/external platform, or safely deferred; no publication action occurs.
- Affected files: README and only factually affected docs; one report in `docs/security/`; `.github/workflows/` if a verified safe workflow is added; changelog.
- Dependencies: Stages 1–2 findings.
- Proposed checkpoint commit: `docs(security): record open source readiness audit`.

### Stage 4 — Final validation and cleanup

- Goal: Recheck the report against source and the full local diff, run proportional checks, update permanent records, close progress.
- Status: pending
- Actions: Re-read TЗ/Definition of Done; run tests and static checks; record precise outcomes and owner actions; remove only this task's progress file after all approved stages are complete.
- Expected result: Concise final report with branch, checkpoints, validation, readiness verdict and release blockers.
- Validation: Full safe deterministic suite and static baseline; no live models/network exposure.
- Completion criterion: All work is committed in focused checkpoints, local branch state understood, no task-owned temp artifact remains.
- Affected files: permanent docs/changelog if needed.
- Dependencies: Stages 1–3.
- Proposed checkpoint commit: `docs(changelog): record readiness audit completion`.

## Decisions

### Preserve licensing and history pending owner decisions

- Context: Root `License` is proprietary/All Rights Reserved and includes a named contact; a maintained GPL Piper dependency is imported in-process; reachable history includes credential-like `.env` data and SQLite chat rows.
- Decision: Do not change `License`, rotate/print values, or rewrite history in this task without a private owner decision. Do not publish/push. Document as release blockers and prepare exact owner actions.
- Reason: TЗ explicitly prohibits automatic publication and destructive history rewriting, and license choice/business model remains owner authority.
- Alternatives: Choose a compatible project license and remove/replace contact details; privately rotate exposed credentials and rewrite history using an approved clean-history plan.
- Consequences: Final readiness cannot exceed `NOT READY` until blockers are resolved and re-audited.

## Progress log

### 2026-10-21 — initial audit

- Stage: readiness report, documentation and quality gates.
- Completed: Read root AGENTS, mandatory subsystem docs, and the pasted TЗ; created requested branch from clean `dev`; inspected release and Git-history posture; completed upload boundary and dependency remediation; made LAN exposure explicit and ordinary startup local-only.
- Changed: Added bounded stream helpers, capped ASR/OCR/criteria/model-transfer uploads, guarded ZIP central-directory/manifest/member processing, cleaned partial temporary uploads, upgraded `python-multipart` to 0.0.31 and Pillow to 13.0.0, raised runtime/setup minimum to Python 3.11, added regression tests, updated supported Python docs, and changed network launcher defaults with an explicit Caddy stop path.
- Validation: Baseline Node 51/51; baseline Python 421/424 with 3 pre-existing failures; stage 1 targeted tests 36/36; stage 2 launcher/setup tests 20/20; `venv/bin/python -m compileall -q app backend tests`, POSIX/zsh syntax, `venv/bin/python -m pip check`, `git diff --check` passed; isolated `pip-audit==2.10.1` scan of `app/requirements.txt` reports no known vulnerabilities. No user data or real model assets used.
- Issues: Historical `.env` credentials and SQLite chat rows remain in reachable history; no values/content printed. No global API authentication remains, including for explicit LAN. Root `License` is proprietary/All Rights Reserved and includes a personal contact address; `piper-tts==1.4.2` is GPL-3.0-or-later. These require owner actions before public release. No source-history secret scanner is installed; release history scan was custom and limited.
- Next action: Read the pasted TЗ deliverables once more, create the evidence report and CI/security workflow, update affected docs and changelog, and preserve unresolved owner actions as release blockers.

## Changed files

### Added

- `temporary/opensource-readiness-audit-progress.md`
- `app/services/upload_limits.py`
- `tests/test_upload_boundaries.py`
- `stop_localgpt_lan.command`
- `stop_localgpt_lan.sh`

### Modified

- `app/requirements.txt`, `app/routes/criteria.py`, `backend/apps/asr/routes.py`, `backend/apps/model_transfer/{import_service.py,manifest.py,router.py}`, `backend/apps/ocr/service.py`
- `run_localgpt.py`, platform launchers/setup entry points, `README.md`, `docs/DEPENDENCIES.md`, `tests/test_setup_dependencies.py`
- `tools/LTrnsrb.sh`, `docs/knowledge/networking.md`, `docs/TESTING.md`, `tests/test_lan_launcher.py`

### Deleted

- None.

## Validation results

- Static checks: Baseline `git diff --check`, `venv/bin/python -m compileall -q app backend tests`, `node --check web_ui/js/app.js`, and `node tests/markdown_rendering.test.mjs` passed.
- Unit/contract tests: Baseline full Python suite: 424 run, 421 passed, 2 ASR pipeline failures and 1 plugin registry error as detailed above; full Node suite: 51/51 passed. Stage 1 targeted Python tests: 36/36 passed.
- Network contract: Stage 2 launcher/setup tests: 20/20 passed; POSIX and zsh syntax checks passed. Actual LAN listener lifecycle was not exercised to avoid changing the user's live network state.
- Dependency audit: Before remediation, pinned `python-multipart==0.0.27` and `Pillow==12.3.0` had known advisories; after updating to 0.0.31 and 13.0.0, isolated `pip-audit -r app/requirements.txt` returned “No known vulnerabilities found”.
- Integration/smoke tests: Not run yet.
- Manual/regression checks: Read-only documentation and source review; findings recorded above and in subsequent updates.
- Skipped checks and reasons: Live model/provider loads; publication and network exposure are explicitly out of scope.
- Remaining uncertainty: Credential validity; exact public-history data review; licensing compatibility/legal interpretation; pip-audit result; clean installs on macOS/Linux/Windows; actual LAN/Tailscale behavior in a second-device network.

## Regressions and deferred work

- New regressions: None found by Stage 1 targeted tests.
- Pre-existing failures: Three full-suite failures listed in `docs/BACKLOG.md`, pending reproduction.
- Resolved issues: None.
- Resolved issues: Unbounded ASR/OCR/criteria/model-transfer upload and ZIP manifest/member processing; temporary-file cleanup on over-limit and validation failures; known vulnerable `python-multipart`/Pillow pins; Python 3.10 dependency compatibility mismatch; implicit macOS LAN startup and absent managed Caddy stop path.
- Unresolved blockers: History credential/data exposure; current proprietary license and contact detail; Piper GPL terms; remote API authentication. Full suite has three baseline failures.
- Deferred/technical debt: Full auth model for private network access; platform matrix outside available host; model/voice per-artifact license catalog.

## Documentation and permanent records

- Architecture/testing/setup docs: Read; factual updates pending source verification.
- Module knowledge docs: Read required subsystem docs; no edits yet.
- Changelog/release notes: Existing `docs/CHANGELOG.md` is canonical; update at completion stage.
- Backlog: Update only if actionable deferred work remains and belongs there.
- Canonical project/task index: `docs/README.md` is the documentation index.

## Checkpoints

Stage 1 checkpoint: `710ec83 fix(security): bound uploads and archive processing`. Stage 2 changes are prepared for `fix(security): make LAN access explicit`; staged diff review and commit are the immediate next action.

## Continuation state

- Current stage: Readiness report, documentation and quality gates.
- Last completed action: Made ordinary macOS startup local-only, stopped managed Caddy on return to local mode, retained explicit LAN start/stop commands, and passed launcher contract checks.
- Current repository state: Stage 1 committed as `710ec83`; Stage 2 source/docs changes on `codex/opensource-readiness-audit`; stage 2 commit pending review; existing tracked multimodal progress preserved.
- Known risks: See risk and decision sections; do not push.
- Next exact action: Review and commit Stage 2; then read the complete pasted TЗ and produce the readiness report/CI/docs/checklist.
- Next command or file: User-pasted TЗ attachment, `.github/workflows/`, `docs/security/`, `docs/CHANGELOG.md`, `docs/README.md`.

## Final checklist

- [ ] Every approved stage is completed.
- [ ] Every acceptance criterion and Definition of Done item is checked or explicitly blocked on owner/platform evidence.
- [ ] Required validation passed or limitations are explicitly accepted.
- [ ] Regressions were compared with baseline.
- [ ] Only affected permanent documentation and records were updated.
- [ ] Deferred work was captured without expanding scope.
- [ ] No unrelated changes or task-owned temporary artifacts remain.
- [ ] Final diff and working-tree state were inspected.
- [ ] Progress file is ready to be deleted.
