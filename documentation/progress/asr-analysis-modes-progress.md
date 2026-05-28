# ASR Analysis Modes Progress

## Original Goal

Improve ASR Studio summary quality after the lightweight-summary thermal fix without returning to heavy default processing.

The next iteration must:

- keep Mac load predictable during ordinary summary tests;
- preserve repeated spoken emphasis instead of treating repeats as cleanup noise;
- let the user provide profile-level ASR analysis context/system prompt;
- add a clear UI analysis-mode selector instead of multiple confusing summary buttons;
- let every ASR pipeline stage be disabled from settings by choosing `Не использовать`;
- avoid meeting-specific hardcoded dictionaries, terms, or business rules.

## Current Status

In progress.

The previous checkpoint was committed as:

- `dcd43ec Stabilize ASR Studio pipeline defaults`

Current uncommitted work started after that checkpoint:

- added profile storage/API surface for `asr.analysis_prompt`;
- added ASR settings textarea markup for `Контекст анализа`;
- wired `Контекст анализа` through UI save/render and backend ASR pipeline settings;
- added the generic repeated-emphasis rule to structurer/summary/retry prompts;
- exposed stage-level `Не использовать` in pipeline model dropdowns.

## Architecture Scope

Relevant areas:

- `backend/apps/asr/pipeline.py` — action routing, stage enabling, summary/structurer prompts, full-analysis gating;
- `app/db.py` — default profile ASR preferences;
- `app/schemas/core.py` and `app/routes/profiles.py` — ASR preference update contract;
- `web_ui/gui_html.html` and `web_ui/js/app.js` — ASR settings UI, analysis-mode selector, stage disabling;
- docs/tests after behavior settles.

## Implementation Stages

### Stage 1 — Persist Profile ASR Analysis Prompt

Goal: add a profile-level ASR prompt/context field, editable in Settings -> ASR.

Completed:

- added `analysis_prompt` to default ASR profile preferences in `app/db.py`;
- added `analysis_prompt` to `AsrPreferencesUpdate`;
- allowed profile preference updates to save trimmed `analysis_prompt`;
- added textarea markup in ASR settings;
- wired textarea value into JS state/render/save flow;
- passed the prompt into ASR pipeline settings/effective context;
- included it in structurer/summary/retry prompts as user profile context, not as hardcoded project logic.

Status: completed for the current checkpoint.

### Stage 2 — Stage Disable Option

Goal: every pipeline stage can be disabled by selecting `Не использовать` in its model dropdown.

Completed:

- introduced UI sentinel value draft: `ASR_PIPELINE_DISABLED_VALUE = "__disabled__"`;
- started adding `Не использовать` as the first option in pipeline model dropdowns;
- finished JS collection logic so disabled stage saves `{ enabled: false, model: previous/default model }`;
- disabled temp/max-token inputs visually when the stage is disabled;
- confirmed the backend path already respects `enabled=false` through `_stage_enabled`.

Pending:

- add/update generic regression coverage for disabled stages if behavior changes further;
- verify reset/default behavior during manual UI testing.

Status: mostly completed for the current checkpoint; regression coverage remains pending.

### Stage 3 — Analysis Mode Selector

Goal: replace separate confusing summary/full buttons with a clear mode selector and one run button.

Planned UI:

- button/dropdown label: `Режим анализа`;
- selected label example: `Режим анализа: Умное саммари`;
- dropdown opens on normal left click;
- entries are mutually exclusive, with a checkmark on the active one.

Planned modes:

- `Быстрое саммари`: raw transcript -> summary.
- `Умное саммари`: raw transcript -> structurer -> summary, recommended for meetings and tasks.
- `Полный анализ`: raw transcript -> segmenter -> roles -> structurer -> summary, available only if full analysis is enabled in settings.

Important decision:

- cleaner must not be part of summary/smart/full analysis by default because it can remove repeated emphasis and smooth away useful speech signals.
- cleaner remains available only as a manual `Очистить текст` action or a user-enabled stage.

Pending:

- define backend action name for smart summary, likely `smart_summary`;
- add UI dropdown and run button;
- map selected mode to backend action;
- keep `Полный анализ` hidden/blocked unless `asr_full_analysis_enabled=true`;
- keep current `Остановить` behavior.

Status: pending for the next implementation pass. Do not start this until the current checkpoint is committed and the user explicitly continues with this stage.

### Stage 4 — Repeated Speech / Importance Signal

Goal: make repeated information count as an importance signal.

Generic rule:

- If a topic/constraint/action is repeated in different words, treat the repetition as evidence of importance.
- Repeated points should be reflected in summary/tasks/current-target state unless contradicted later.
- Do not collapse repeated technical explanations into generic vague wording.

Important:

- This must be a generic prompt/QA rule.
- Do not add meeting-specific words, company names, domain examples, market/feed examples, or hardcoded dictionaries.

Completed:

- added this rule to structurer/summary/retry prompts;
- included profile `analysis_prompt` near this rule so user role/context can guide interpretation.

Pending:

- user manual test on a different meeting transcript;
- tune wording only if manual tests show generic failures.

Status: implemented generically for the current checkpoint; live quality testing remains user-side.

### Stage 5 — Docs, Tests, Cleanup

Pending:

- update README/TECHNICAL docs after final behavior is implemented;
- add only generic tests, no real-meeting hardcoded content;
- run safe syntax checks;
- do not run live ASR/LLM summary tests unless user explicitly asks;
- remove this progress file when the task is fully complete.

## Completed Tasks

- Created this progress file.
- Captured the agreed UX and architecture direction.
- Captured the decision to keep cleaner out of default analysis modes.
- Added profile-level ASR analysis context setting.
- Wired ASR analysis context through UI, API, profile preferences, and ASR pipeline prompts.
- Added generic repeated-emphasis handling to structurer/summary/retry prompts.
- Added UI support for selecting `Не использовать` for pipeline stages.

## In Progress Tasks

- Preparing a checkpoint commit for the current partial implementation.

## Pending Tasks

- Implement `Режим анализа` dropdown and run button.
- Implement `smart_summary` backend action.
- Decide how current `summary`, `tasks`, and `full` actions should map to the new modes.
- Exclude cleaner from default analysis modes only after mode routing is explicit.
- Update docs/tests.
- Remove this progress file after completion.

## Architecture Decisions

- Do not delete cleaner code now.
- Cleaner is not a default analysis stage.
- Cleaner remains a manual operation and can be disabled/enabled through stage settings.
- Stage disabling is generic: select `Не использовать` instead of adding stage-specific flags.
- ASR analysis context is profile-level user configuration, not hardcoded runtime behavior.
- `Умное саммари` should improve semantic extraction without role resolution.
- No meeting-specific dictionaries or transcript-specific hardcoding.

## Changed Files

Currently changed in this task:

- `app/db.py`
- `app/routes/profiles.py`
- `app/schemas/core.py`
- `backend/apps/asr/pipeline.py`
- `web_ui/gui_html.html`
- `web_ui/js/app.js`
- `documentation/progress/asr-analysis-modes-progress.md`

## Found Issues

- Lightweight summary reduced thermal load, but quality can miss repeated emphasis and technical role context.
- Cleaner can remove exactly the repetitions that the user intentionally uses as importance signals.
- Separate action buttons are becoming confusing; user needs one explicit analysis mode selector.

## Technical Debt

- Existing action naming (`summary`, `tasks`, `full`) does not fully express UX intent.
- Pipeline settings have stage enable flags internally, but UI did not expose a clear `Не использовать` model choice.
- Profile ASR prompt was missing; chat system prompt is not enough for ASR analysis.

## Next Steps

1. Finish checkpoint commit for current work.
2. Add `Режим анализа` dropdown and run button in the next pass.
3. Implement backend `smart_summary` action in the next pass.
4. Keep live ASR/LLM tests user-side because of thermal risk.
5. Update docs/tests once the mode behavior is stable.
