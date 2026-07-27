# Model Export Selection Modal

## Original Task
- Goal: move model selection out of the System settings card into a modal opened by `Экспорт моделей`.
- Acceptance criteria:
  - System settings show compact adjacent export/import actions without an expanded model list.
  - Clicking export opens a modal containing the current complete-model inventory.
  - The modal supports individual selection, select all/clear all, selected count and unique-size summary.
  - Export starts only after explicit confirmation with at least one selected model.
  - Closing by button, backdrop, or Escape makes no model/storage changes and restores focus.
  - Desktop/mobile, dark/light, keyboard behavior and static UI tests are verified.
- Source request: user message in the active Codex task.

## Task Analysis
- Architecture scope: active static UI only; backend model-transfer API and archive contract remain unchanged.
- Affected areas/files: `web_ui/gui_html.html`, `web_ui/js/app.js`, `web_ui/css/style.css`, `tests/model_transfer_ui.test.mjs`; permanent UI documentation only if its current description becomes inaccurate.
- Constraints and risks: settings are already a modal, so the export dialog must layer above it, preserve scroll lock, avoid duplicate inventory requests, and keep focus behavior accessible. Real export must not run during QA.

## Documentation Impact Review
- Outcome: Required.
- Documents to update / reason: `docs/knowledge/ui.md` currently says the export preview selects units in the System tab and must describe the modal selection flow. `docs/CHANGELOG.md` is the project’s existing canonical compact change index; no duplicate `documentation/change-index.md` will be created.

## Implementation Stages

### Stage 1 — Modal UI and Interaction
- Goal: replace the inline inventory with an accessible export-selection modal and wire selection state.
- Related files: `web_ui/gui_html.html`, `web_ui/js/app.js`, `web_ui/css/style.css`, `tests/model_transfer_ui.test.mjs`.
- [x] Completed: acceptance criteria and current active UI boundaries reviewed.
- [x] Completed: inspected and reused existing modal/focus conventions.
- [x] Completed: implemented modal markup, responsive styles, selection state and explicit confirmation.
- [x] Completed: removed the expanded inventory and manual refresh control from the System card.
- Architectural decisions: keep `/model-transfer/export-preview` and `/model-transfer/exports` unchanged; fetch inventory automatically and present it only when export is requested.
- Problems: none.
- Technical debt: none identified.
- Next steps: create the Stage 1 checkpoint, then update affected documentation and run the final baseline.
- Validation: `node --check web_ui/js/app.js` passed; `node --test tests/model_transfer_ui.test.mjs` passed 4/4; `git diff --check` passed. Live `:8001` checks passed at 1280×720 and 390×844 in dark/light themes: 12 models, no horizontal overflow, select-all/individual selection, disabled empty confirmation, Escape close and focus return. No export was started.
- Git checkpoint: pending.

### Stage 2 — QA, Documentation & Cleanup
- Goal: verify live behavior without starting an export, update affected docs, and remove this file.
- Related files: `docs/knowledge/ui.md`, `docs/CHANGELOG.md`.
- [x] Completed: desktop/mobile, dark/light and keyboard checks.
- [ ] Pending: permanent documentation update.
- [ ] Pending: final cleanup commit removing this progress file.
- Architectural decisions: none yet.
- Problems: none.
- Technical debt: none.
- Next steps: checkpoint Stage 1, update UI docs/changelog, run final validation, remove progress file.
- Validation: pending.
- Git checkpoint: pending.

## Overall Status
- Status: in progress.
- Completed: request analysis, documentation-impact review, modal implementation and live UI QA.
- In progress: Stage 1 checkpoint preparation.
- Pending: permanent documentation, final validation and cleanup.
- Changed files: `docs/progress/model-export-selection-modal-progress.md`, `web_ui/gui_html.html`, `web_ui/js/app.js`, `web_ui/css/style.css`, `tests/model_transfer_ui.test.mjs`.
- Known problems: none.
- Technical debt: none.
- Next action: create the Stage 1 checkpoint commit.
- Latest Git checkpoint: `17f8b88` — Load model export inventory automatically.

## Continuation Prompt
Continue work on `model-export-selection-modal` using `docs/progress/model-export-selection-modal-progress.md`. Read the progress file, current Git status, and latest checkpoint commit first. Current status: modal implementation and live QA are complete, awaiting the Stage 1 checkpoint. Completed: compact System card, export-selection modal, select-all/individual selection, responsive and keyboard checks. Remaining: checkpoint, UI docs/changelog, final validation and cleanup. Problems/blockers: none. Decisions to preserve: backend API remains unchanged; no real export during QA; use the existing project changelog instead of creating a duplicate change index. Latest checkpoint: `17f8b88`. Perform next: commit Stage 1, then finish Stage 2.
