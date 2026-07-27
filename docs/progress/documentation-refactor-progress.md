# Documentation Refactor Progress

## Original Task Goal

- Reorganize, consolidate, and verify LocalGPT documentation against the current code.
- Replace overlapping root and `documentation/` documents with a compact `docs/` architecture and a root `AGENTS.md`.
- Preserve runtime Markdown files and the separate AI Coding Retrieval Stack specification.
- Work in the user-selected branch `update_project_docs` and create five stage commits with the exact messages from the technical specification.

## Current Status

- Status: Stage 4 agent workflow migration implemented; validation and checkpoint pending.
- Completed: Stages 1–3 committed; `AGENTS.md` completed; old GPT instruction variants removed; active ASR progress moved to `docs/progress/` with self-references updated.
- In progress: validating `AGENTS.md` as a standalone entry point and checking old progress/instruction references.
- Pending: final validation, cleanup, documentation-refactor progress removal, and Stage 5 checkpoint.
- Branch note: the specification names `update-documentation`, while the user explicitly selected `update_project_docs`; the explicit user choice is authoritative.

## Architecture Scope

- Runtime entry: `run_localgpt.py` launches `uvicorn` with `backend.server:app`; `app/server.py` is a compatibility import.
- API composition: `backend/server.py` mounts shared `app/routes/*` plus mini-app routers from `backend/apps/{chat,asr,tts,ocr,rag,plugins}` and serves `web_ui/`.
- Transitional boundary: feature routes/services mostly live under `backend/apps/`; configuration, database, profiles, storage, schemas, and selected shared services remain under `app/`.
- Active frontend: `web_ui/gui_html.html`, `web_ui/js/app.js`, modular supporting JS, and CSS under `web_ui/css/`.
- Providers: chat model routing and Ollama runtime are backend services; TTS exposes an abstract provider contract with a Piper implementation; ASR selects whisper.cpp or faster-whisper from configuration.
- Storage: SQLite in `app/db/`, project-scoped model/cache directories under `models/`, profile-scoped RAG sources under `rag_sources/`, and generated artifacts under ignored runtime directories.
- Networking: localhost runtime by default, LAN access through Caddy, and private-tailnet access through the trusted Tailscale handler.
- Legacy/reference: `compare-branch/` is a read-only reference and is not imported by runtime code; `app/` remains a compatibility/shared layer during migration.

## Documentation Inventory

Inventory method: `rg --files` over Markdown, text, prompt, README, testing, cleanup, backlog, and progress files; code references checked with `rg`; duplicates compared by source markers, headings, and content hashes.

### Canonical/runtime files to keep

| Path | Purpose / audience | Audit result | Action |
| --- | --- | --- | --- |
| `app/prompts/system_base.md` | Runtime system prompt | Loaded by `app/roles.py` through `PROMPTS_DIR`; active | Keep beside runtime code and link from architecture |
| `app/requirements.txt` | Python dependency manifest | Used by `run_localgpt.py`; not prose documentation | Keep unchanged |
| `plugins/tailscale/plugin.json` docs entries | Plugin-local documentation contract | Runtime registry validates these paths | Keep plugin-local README/docs; link from knowledge docs |
| `plugins/README.md` | Plugin directory contract | Concise local boundary document | Keep as component-local README |
| `plugins/tailscale/README.md` | Tailscale plugin entry | Referenced by manifest | Keep |
| `plugins/tailscale/docs/*.md` | User and technical Tailscale help | Referenced by manifest and served by plugin API | Keep as plugin-owned docs; avoid copying their full content |
| `rag_sources/README.md` | Runtime data-folder contract | Explains profile source files and indexing format | Keep as component-local README |
| `backend/README.md` | Current backend map | Accurate but overlaps target knowledge docs | Migrate verified content, then remove |

### Root and documentation-hub files to consolidate

| Path(s) | Purpose / audience | Audit result | Action |
| --- | --- | --- | --- |
| `README.md`, `documentation/README.project.md` | Project overview and operations | Large overlapping copies; root mixes architecture, changelog, UI, and operations | Rewrite root README; migrate details to target docs; remove hub copy |
| `TECHNICAL_README.md`, `documentation/TECHNICAL_README.md` | Technical architecture | Near-copy hub model; current but too broad | Split verified facts across `ARCHITECTURE.md`, `TESTING.md`, and knowledge docs; remove both |
| `Instructions_for_GPT*.md`, `documentation/Instructions_for_GPT*.md` | Coding-agent handoff rules | Three overlapping variants plus hub copies; paths and workflow are obsolete | Consolidate into root `AGENTS.md`, then remove |
| `CLEANUP_REPORT.md`, `documentation/CLEANUP_REPORT.md` | Historical cleanup summary | Mostly completed work plus remaining debt | Move durable debt to `BACKLOG.md`, significant result to `CHANGELOG.md`, then remove |
| `documentation/README.backend_structure.md` | Backend hub copy | Derived from `backend/README.md` | Consolidate into `knowledge/backend.md`, then remove |
| `documentation/README.rag.md` | RAG hub copy | Derived from `rag_sources/README.md` | Consolidate architecture into `knowledge/rag.md`; retain runtime-folder README; remove hub copy |
| `docs/ui-components.md`, `documentation/ui-components.md` | UI component conventions | Source plus hub copy; useful but over-specific as a standalone root doc | Consolidate into `knowledge/ui.md`, then remove both |
| `documentation/plugin-architecture.md` | Plugin Registry v0 architecture | Subsystem-specific and current | Consolidate into `knowledge/plugins.md`, then remove |
| `documentation/remote-access-tailscale.md`, `documentation/how-to-use-tailscale-mode.md` | Remote-access hub copies | Duplicate plugin-owned docs | Consolidate overview/troubleshooting into `knowledge/networking.md`; remove hub copies |
| `documentation/README.md`, `documentation/map.md` | Old documentation hub and map | Navigation points to duplicate copies and old paths | Replace with `docs/README.md`; remove old hub |
| `documentation/backlog.md` | Future work | Contains valid debt plus task-specific framing | Curate into `docs/BACKLOG.md`, then remove |
| `documentation/change-index.md` | Compact completed-work index | Useful history but located in deprecated hub | Fold durable entries into `docs/CHANGELOG.md`; remove old hub |
| `documentation/system_base.prompt.md` | Copy of runtime prompt | Duplicate and not loaded by runtime | Link to canonical runtime prompt, then remove copy |

### Progress and reference files

| Path / group | Status | Action |
| --- | --- | --- |
| `documentation/progress/asr-analysis-modes-progress.md` | Active: explicitly says not to delete until user confirmation; later commits and change index confirm continuing ASR/RAG work | Move to `docs/progress/` during agent-workflow migration; do not delete |
| `docs/progress/documentation-refactor-progress.md` | Active temporary record for this task | Track in stage commits; delete in Stage 5 |
| `compare-branch/**` documentation (26 files) | Read-only historical/reference snapshots; runtime does not import them | Inventory as one reference group; keep unchanged until the existing parity-removal debt is separately approved |

No repository file matching an AI Coding Retrieval Stack specification was found by filename/content-oriented candidate search. The user-provided specification explicitly excludes it; therefore no retrieval-stack specification is created, edited, renamed, or deleted.

## Migration Matrix

| Current source | Target source of truth | Planned disposition |
| --- | --- | --- |
| Root `README.md` + project overview sections | `README.md` | Rewrite compactly |
| Technical overview + old map | `docs/ARCHITECTURE.md` | Verify and consolidate |
| Backend structure docs | `docs/knowledge/backend.md` | Verify and consolidate |
| TTS/chat model provider contracts | `docs/knowledge/providers.md` | Document from code |
| Plugin architecture + trusted handler docs | `docs/knowledge/plugins.md` | Verify and consolidate |
| RAG source docs + service implementation | `docs/knowledge/rag.md` | Verify and consolidate |
| UI components + active HTML/JS/CSS | `docs/knowledge/ui.md` | Verify and consolidate |
| LAN/Tailscale/Caddy docs and launchers | `docs/knowledge/networking.md` | Verify and consolidate |
| Test notes embedded in README/technical docs | `docs/TESTING.md` | Consolidate commands and coverage |
| Cleanup/change history | `docs/CHANGELOG.md` | Curate durable results only |
| Backlog and cleanup debt | `docs/BACKLOG.md` | Curate unresolved work only |
| GPT instruction variants | `AGENTS.md` | Consolidate workflow and Definition of Done |
| Old docs hub/map | `docs/README.md` | Replace with concise navigation |
| `documentation/progress/asr-analysis-modes-progress.md` | `docs/progress/asr-analysis-modes-progress.md` | Move without changing task state |
| `documentation/system_base.prompt.md` | `app/prompts/system_base.md` | Remove duplicate; link canonical runtime file |

## Implementation Stages

### Stage 1 — Documentation Audit and Project Inventory

- [x] Reviewed the complete technical specification.
- [x] Confirmed active branch and clean starting worktree.
- [x] Inventoried all non-reference documentation and the `compare-branch/` reference group.
- [x] Verified runtime prompt loading through `app/roles.py`.
- [x] Mapped active backend, frontend, providers, RAG, plugins, networking, storage, and tests.
- [x] Classified the existing progress file as active.
- [x] Confirmed no source-code change is part of this stage.
- Validation: documentation/runtime inventory completed; runtime prompt reference verified; `git diff --check` passed; only Stage 1 tracking files changed.
- Git checkpoint: `8a87bc2` — `stage 1: audit current documentation`.

### Stage 2 — Establish Documentation Architecture

- [x] Created the target `docs/` and `docs/knowledge/` files with non-overlapping ownership.
- [x] Created a root `AGENTS.md` foundation and documentation navigation.
- [x] Validated every relative link in the new skeleton.
- Architectural decisions: project-wide permanent docs live in `docs/`; component-owned README files remain beside their runtime/configuration directories; explicit `Pending migration` markers are temporary and must be removed by Stage 5.
- Validation: 13 target/entry Markdown files checked; all relative targets exist; `git diff --check` passed; no project `skills/` directory; runtime prompt remains unchanged.
- Git checkpoint: `39ba7a5` — `stage 2: establish documentation architecture`.

### Stage 3 — Consolidate and Rewrite Documentation

- [x] Rewrote the root README and filled target documents from code-verified sources.
- [x] Removed only fully replaced duplicate documents.
- [x] Preserved runtime prompt, dependency manifest, plugin-owned docs, RAG folder docs, active ASR progress, and `compare-branch/`.
- [x] Ran safe application smoke and documentation checks.
- Architectural decisions: root README contains only product overview/startup; project-wide subsystem details live in `docs/knowledge/`; manifest-owned plugin docs and runtime-folder RAG docs remain canonical locally.
- Validation: all 27 project Markdown files have valid relative targets; isolated `/health` + `/ui/gui_html.html` smoke passed on a temporary SQLite DB; `node --check web_ui/js/app.js` and both Markdown renderer tests passed; full Python suite ran 160 tests with 157 passing and three pre-existing failures recorded below; `git diff --check` and runtime-preservation checks passed.
- Git checkpoint: `37bd1b6` — `stage 3: consolidate project documentation`.

### Stage 4 — Migrate Agent Documentation Workflow

- [x] Finished `AGENTS.md`, including task-specific reading, progress tracking, affected-documents policy, testing, legacy rules, forbidden actions, and Definition of Done.
- [x] Moved the active ASR progress file to `docs/progress/` and updated its self-references.
- [x] Removed obsolete GPT instruction variants after transferring their durable constraints.
- [x] Validated the standalone entry point and absence of deprecated paths.
- Architectural decisions: `AGENTS.md` owns workflow only; it links to architecture/knowledge rather than duplicating them. Active task records survive a documentation refactor and are moved without changing their completion state.
- Validation: all 21 current project Markdown files have valid relative link targets; required `AGENTS.md` sections are present; active ASR progress self-references use `docs/progress/`; no deprecated progress path remains in the active record; runtime prompt hash is unchanged; `git diff --check` and no-project-skills checks passed.
- Git checkpoint: pending — `stage 4: migrate agent documentation workflow`.

### Stage 5 — Validation, Cleanup and Finalization

- [ ] Validate structure, Markdown links, runtime paths, test commands, and subsystem claims.
- [ ] Run proportionate regression tests without invoking live ASR/LLM/Ollama workloads.
- [ ] Finalize changelog/backlog, remove deprecated hub artifacts and this progress file, and leave the worktree clean.
- Git checkpoint: pending — `stage 5: validate and finalize documentation`.

## Architectural Decisions

- Use `docs/` as the only project-wide permanent documentation hub; keep component-local README files only where runtime folders or plugin manifests own them.
- Treat `app/prompts/system_base.md` as runtime configuration, not project documentation.
- Preserve `compare-branch/` as an explicitly read-only reference because its removal is separate technical debt and outside this refactor.
- Preserve the active ASR progress record and migrate only its path.
- Do not create a project `skills/` directory.
- Prefer links to canonical component docs over duplicated user instructions.

## Changed Files

- `.gitignore`
- `AGENTS.md`
- `docs/README.md`
- `docs/ARCHITECTURE.md`
- `docs/TESTING.md`
- `docs/CHANGELOG.md`
- `docs/BACKLOG.md`
- `docs/knowledge/backend.md`
- `docs/knowledge/providers.md`
- `docs/knowledge/plugins.md`
- `docs/knowledge/rag.md`
- `docs/knowledge/ui.md`
- `docs/knowledge/networking.md`
- `docs/progress/.gitkeep`
- `docs/progress/asr-analysis-modes-progress.md` (moved from deprecated path; still active)
- `docs/progress/documentation-refactor-progress.md`

## Found Problems

- The repository maintains multiple root/hub copies with small drift, so source-of-truth ownership is unclear.
- Root `README.md` and `TECHNICAL_README.md` combine overview, architecture, test snapshots, change history, UI guidance, and operational details.
- The active progress record uses the deprecated `documentation/progress/` path.
- The technical specification's branch name differs from the user's selected branch.
- The active frontend remains concentrated in a large `web_ui/js/app.js` and `web_ui/css/style.css`; this is existing technical debt, not documentation-refactor scope.

## Technical Debt

- `compare-branch/` removal requires a separate parity checklist and explicit approval.
- Legacy `LTrnsrb.*` launch aliases remain until the modern launcher flow is confirmed.
- Shared/core code remains split between `app/` and `backend/apps/`.
- Large frontend files need a future modularization task.
- External plugin process API, marketplace, hot reload, and a potential Caddy plugin remain unimplemented by design.

## Regression Issues

- Documentation changes introduced no source-code regression.
- Full Python discovery currently reports:
  - `test_full_analysis_skips_cleaner_by_default_and_sanitizes_speakers`: mocked responses no longer match current full-pipeline stage/validation behavior.
  - `test_pipeline_tasks_are_normalized_for_transcript_record`: mocked task payload no longer reaches the expected normalized task list.
  - `test_get_plugin_doc_reads_manifest_doc_only`: passes in isolation, but fails after the full suite because restored DB state lacks `app_settings`.
- The two ASR failures reproduce in isolation; the plugin-doc failure does not. These issues predate and are unrelated to documentation-only changes, so they were added to `docs/BACKLOG.md` rather than fixed outside scope.

## Next Steps

1. Validate Stage 4 links, required workflow sections, and deprecated path removal.
2. Create the exact Stage 4 checkpoint commit.
3. Run final Stage 5 structure/link/test checks, finalize changelog/backlog, and delete only this documentation-refactor progress file.

## Continuation Prompt

Continue the LocalGPT documentation refactor in branch `update_project_docs`. Read `docs/progress/documentation-refactor-progress.md`, `git status`, and commits `8a87bc2`, `39ba7a5`, `37bd1b6` first. Stage 4 is implemented: `AGENTS.md` is complete, old GPT instruction variants are removed, and the active ASR record is moved to `docs/progress/asr-analysis-modes-progress.md` without closing it. Validate Stage 4 and commit as `stage 4: migrate agent documentation workflow`. Then run Stage 5 final structure/link/smoke checks, retain the documented unrelated test failures in backlog, remove only `docs/progress/documentation-refactor-progress.md`, and commit as `stage 5: validate and finalize documentation`. Preserve the active ASR progress, `app/prompts/system_base.md`, `compare-branch/`, plugin-local docs, and `rag_sources/README.md`. Do not edit any AI Coding Retrieval Stack specification or create project skills.
