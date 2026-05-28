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
- started implementation of the ASR Studio `Режим анализа` selector and backend `smart_summary` action.

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

Implemented in this pass:

- added backend action `smart_summary`;
- mapped `summary` to fast raw-transcript summary without cleaner;
- mapped `smart_summary` to structurer -> summary without cleaner and without speaker resolver;
- mapped `full` to segmenter -> speaker resolver -> structurer -> summary, still gated by `asr_full_analysis_enabled`;
- added one ASR Studio `Режим анализа` selector and one `Запустить анализ` button;
- kept manual `Очистить` separate from the normal analysis modes;
- kept `Остановить` behavior unchanged.

Status: implemented; safe checks and docs still pending.

Current implementation note:

- selector implementation is now starting in this pass;
- `Умное саммари` must route raw transcript/chunks through structurer -> summary when those stages are enabled;
- `Умное саммари` must not run cleaner or speaker resolver by default;
- `Полный анализ` remains gated by `asr_full_analysis_enabled`;
- stage `enabled=false` from user settings has absolute priority over every analysis mode.

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
- Implemented `Режим анализа` selector and run button in ASR Studio.
- Implemented backend `smart_summary`.
- Mapped `summary` to fast raw -> summary and kept `full` gated.
- Added generic regression tests for action routing, disabled summary/structurer stages, smart summary routing, and full-analysis gating.
- Updated README/technical/backend docs for ASR analysis modes, `Не использовать`, optional cleaner, full-analysis gating, and ASR analysis context.
- Passed safe checks: `py_compile`, `node --check`, `git diff --check`, and selected mocked ASR pipeline unit tests.
- Added profile-level `asr.analysis_language` with `auto`, `ru`, `en`.
- Added top-toolbar ASR Studio `Язык summary` selector after `Язык / prompt`.
- Changed ASR Studio `Настройки анализа` button text to `Настройки`.
- Updated structurer/summary/retry prompts to use the selected or auto-detected output language.
- Added generic mocked tests for auto Russian detection and manual English override.
- Re-ran safe checks for language changes: `py_compile`, `node --check`, `git diff --check`, and 10 selected mocked ASR pipeline tests.
- Added a generic summary grounding guard for instruction echoes, service markers, language mismatch, and outputs that are not connected to transcript/structured evidence.
- Added a grounding retry before saving summary results; if the retry still fails validation, the pipeline returns a clear `asr_summary_grounding_failed` error instead of saving fabricated summary text.
- Added generic mocked tests for grounding retry success and grounding failure without meeting-specific transcript content.
- Re-ran safe checks for grounding changes: `py_compile`, `node --check`, `git diff --check`, and 12 selected mocked ASR pipeline tests.

## In Progress Tasks

- Waiting for user-side manual ASR/LLM validation of the new language and grounding behavior before closing the task.

## Pending Tasks

- Ensure selected output language applies to the whole ASR result, including structured fallback blocks and UI diagnostics, so English summary is not mixed with Russian `## Тема`/`Предупреждения` blocks.
- Next stage: improve ASR result rendering without changing pipeline behavior yet.
- Render ASR summary output as formatted Markdown instead of raw markdown text with visible `**bold**`, headings and bullets.
- Keep copy/download behavior as plain text or markdown so the source content is not lost.
- Separate pipeline diagnostics/warnings from the summary body in UI.
- Convert technical warnings such as `raw_transcript_chunked:2` into human-readable UI text like `Transcript обработан в 2 чанка`.
- Consider a later lightweight `Перевести summary` action that translates the already generated summary without rerunning ASR/structurer/full pipeline.
- If translation is added, make it a separate explicit LLM call and store/display it as a language-specific summary variant.
- Keep live ASR/LLM tests user-side because of thermal risk.
- Manual user-side ASR/LLM quality testing, if needed.
- Remove this progress file after completion.

## Architecture Decisions

- Do not delete cleaner code now.
- Cleaner is not a default analysis stage.
- Cleaner remains a manual operation and can be disabled/enabled through stage settings.
- Stage disabling is generic: select `Не использовать` instead of adding stage-specific flags.
- User stage settings have absolute priority: an analysis mode may recommend a route, but must not override `enabled=false`.
- ASR analysis context is profile-level user configuration, not hardcoded runtime behavior.
- `Умное саммари` should improve semantic extraction without role resolution.
- No meeting-specific dictionaries or transcript-specific hardcoding.

## Changed Files

Currently changed in this task:

- `README.md`
- `TECHNICAL_README.md`
- `backend/README.md`
- `app/db.py`
- `app/routes/profiles.py`
- `app/schemas/core.py`
- `backend/apps/asr/pipeline.py`
- `documentation/README.backend_structure.md`
- `documentation/README.project.md`
- `documentation/TECHNICAL_README.md`
- `tests/test_pipeline_memory.py`
- `web_ui/css/style.css`
- `web_ui/gui_html.html`
- `web_ui/js/app.js`
- `documentation/progress/asr-analysis-modes-progress.md`

## Found Issues

- Lightweight summary reduced thermal load, but quality can miss repeated emphasis and technical role context.
- Cleaner can remove exactly the repetitions that the user intentionally uses as importance signals.
- Separate action buttons are becoming confusing; user needs one explicit analysis mode selector.
- Manual test produced an English summary from a Russian transcript despite Russian-oriented prompts; ASR summary language needs an explicit auto/manual setting.
- Manual test produced a fabricated English toy conversation (`Speaker 1: Hello! How are you?`) instead of summarizing the provided transcript. Added generic grounding validation/retry so this class of output is rejected before saving.

## Technical Debt

- Existing action naming (`summary`, `tasks`, `full`) does not fully express UX intent.
- Legacy action names remain supported, but UI now presents a single explicit mode selector.

## Next Steps

1. Next implementation pass should focus on ASR result rendering/diagnostics separation.
2. Keep live ASR/LLM tests user-side because of thermal risk.
3. Review manual ASR Studio behavior on a real transcript when the user is ready.
4. Remove this progress file only after the user confirms the task can be closed.
