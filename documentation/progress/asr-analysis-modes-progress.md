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
- Manual ASR/LLM validation showed a weaker but still bad summary class: generic dialogue overview with `Speaker 1/2` artifacts, a self-limiting disclaimer, and no required ASR summary markdown sections.
- Added generic summary format/quality validation: required `## Краткое резюме` / `## Brief Summary` heading, rejection of placeholder speaker identities, generic dialogue-overview output, participant/language metadata blocks, and limitation disclaimers.
- Added a mocked regression test for this generic overview failure and re-ran safe checks plus 13 selected mocked ASR pipeline tests.
- Manual ASR/LLM validation then showed the stricter guard could end with a slow `asr_summary_grounding_failed` error after retry.
- Added a safe structured-evidence fallback for `smart_summary`/`full`: when structurer evidence exists and summary validation fails, backend assembles a markdown summary from structured data without another LLM retry and without saving fabricated text.
- Added a mocked regression test for structured fallback and re-ran safe checks plus 14 selected mocked ASR pipeline tests.
- Found that ASR pipeline requests were still tied to the selected chat model in UI and defaulted to `pipeline_num_gpu=0`, forcing Ollama CPU-only for ASR LLM stages.
- Started ASR runtime isolation/load-control implementation:
  - ASR pipeline settings now use dedicated model settings key `__asr_pipeline__` instead of the selected chat model;
  - default ASR pipeline no longer sends `ollama_num_gpu=0`; Ollama keeps its normal auto/GPU behavior unless `OLLAMA_PIPELINE_NUM_GPU` is explicitly set;
  - default summary model changed from `mistral-nemo:12b` to `qwen3:8b` to avoid loading two large models for common smart summary;
  - added a narrow profile-preferences migration for old default `mistral-nemo:12b` summary settings so existing profiles pick up the new ASR default unless they use explicit model_settings overrides;
  - added profile-level ASR diagnostics logging toggle with profile log-folder creation/removal;
  - added mocked tests for the dedicated ASR settings slot, auto GPU default and diagnostics folder/log behavior.
- Safe verification passed after this pass:
  - `venv/bin/python -m py_compile app/config.py app/db.py app/routes/profiles.py app/schemas/core.py backend/apps/asr/pipeline.py tests/test_pipeline_memory.py`;
  - `node --check web_ui/js/app.js`;
  - 16 selected mocked ASR pipeline/unit tests;
  - `git diff --check`.
- Manual stop validation showed Ollama can leave `qwen3:8b` in `Stopping...` while its runner keeps consuming CPU after UI/backend stop.
- Added emergency ASR stop fallback:
  - `/asr/stop` now calls a bounded `force_unload_models` helper;
  - helper unloads target ASR pipeline models, waits briefly, checks loaded Ollama models, and sends `SIGTERM` to stuck `ollama runner` processes when target models remain loaded;
  - stop response now includes `stuck_models`, `terminated_runner_pids`, and `terminate_failed_pids` for clear diagnostics;
  - added mocked tests for stuck-runner termination and no-kill clean unload path.
- Manual stop validation after a new `qwen3:8b` stuck run:
  - before stop: `ollama ps` showed `qwen3:8b` at `100% CPU`, `Stopping...`, runner PID `24867`;
  - `/asr/stop` returned `stuck_models:["qwen3:8b"]` and `terminated_runner_pids:[24867]`;
  - after stop: `ollama ps` was empty and PID `24867` no longer existed.
- Manual ASR test showed `qwen3:8b` still consumed high CPU and a long `smart_summary` run failed only because summary validation reported `summary_missing_required_heading`.
- Added explicit Ollama thinking controls:
  - chat topbar now has a compact `Thinking` dropdown for thinking-capable models, with `Включено`/`Выключено` choices and a stable purple visual style;
  - model settings persist `ollama_think`;
  - ChatService passes top-level `think` to native Ollama `/api/chat`;
  - ASR pipeline settings expose `Thinking LLM стадий`;
  - ASR LLM stages default to `think:false` unless the user explicitly overrides the ASR setting.
- Reduced avoidable ASR retry/load:
  - summary QA now repairs a missing required `## Краткое резюме` / `## Brief Summary` heading locally when the summary body is otherwise usable;
  - missing heading alone no longer causes a second summary LLM call or a 502 validation failure.
- Added generic mocked tests for native `think:false` payloads, ASR default thinking-off behavior, and missing-heading repair without retry.
- Safe verification passed for the thinking/heading pass:
  - `venv/bin/python -m py_compile app/config.py app/db.py app/routes/profiles.py app/schemas/core.py backend/apps/chat/service.py backend/apps/chat/routes.py backend/apps/chat/services/ollama_runtime.py backend/apps/asr/pipeline.py tests/test_model_router.py tests/test_pipeline_memory.py`;
  - `node --check web_ui/js/app.js`;
  - `git diff --check`;
  - `venv/bin/python -m unittest tests.test_model_router tests.test_pipeline_memory` passed 111 mocked/unit tests.
- User-side validation found that `Режим анализа: Умное саммари` still drives Ollama as CPU-heavy even after removing the old explicit `pipeline_num_gpu=0`.
- Root cause under investigation/fix: ASR pipeline `auto` GPU mode currently omits `num_gpu`, which does not guarantee full Metal offload on Apple Silicon, and shared Ollama Metal recovery can silently fall back to a CPU payload.
- Completed a runtime fix:
  - ASR pipeline should prefer explicit Apple Silicon Metal offload by default;
  - ASR pipeline should not silently use CPU fallback when Metal fails;
  - chat/runtime CPU fallback can remain available for normal chat unless explicitly disabled.
- Implementation details:
  - Apple Silicon default `OLLAMA_PIPELINE_NUM_GPU` is now `999` when the env var is unset;
  - `OLLAMA_PIPELINE_NUM_GPU=auto` still omits `ollama_num_gpu` for Ollama-native auto behavior;
  - ASR pipeline passes `ollama_allow_cpu_fallback=false` for LLM stages;
  - shared Ollama runtime supports per-request CPU fallback disabling while preserving chat fallback defaults.
- Safe verification completed:
  - `py_compile` for changed Python files;
  - `node --check web_ui/js/app.js`;
  - selected mocked runtime/ASR tests;
  - `git diff --check`.

## In Progress Tasks

- Await user-side manual ASR/summary validation after runtime isolation and emergency stop fallback.
- Await user-side manual ASR validation that `Умное саммари` no longer starts a CPU-only Ollama runner.

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
- `app/config.py`
- `app/db.py`
- `app/routes/profiles.py`
- `app/schemas/core.py`
- `backend/apps/asr/pipeline.py`
- `documentation/TECHNICAL_README.md`
- `tests/test_pipeline_memory.py`
- `web_ui/gui_html.html`
- `web_ui/js/app.js`
- `documentation/progress/asr-analysis-modes-progress.md`

## Found Issues

- Lightweight summary reduced thermal load, but quality can miss repeated emphasis and technical role context.
- Cleaner can remove exactly the repetitions that the user intentionally uses as importance signals.
- Separate action buttons are becoming confusing; user needs one explicit analysis mode selector.
- Manual test produced an English summary from a Russian transcript despite Russian-oriented prompts; ASR summary language needs an explicit auto/manual setting.
- Manual test produced a fabricated English toy conversation (`Speaker 1: Hello! How are you?`) instead of summarizing the provided transcript. Added generic grounding validation/retry so this class of output is rejected before saving.
- Manual test then produced a grounded but low-quality generic dialogue overview with `Speaker 1/2` participant artifacts and a disclaimer. Added generic summary format/quality validation and retry for this class.

## Technical Debt

- Existing action naming (`summary`, `tasks`, `full`) does not fully express UX intent.
- Legacy action names remain supported, but UI now presents a single explicit mode selector.

## Next Steps

1. Next implementation pass should focus on ASR result rendering/diagnostics separation.
2. Keep live ASR/LLM tests user-side because of thermal risk.
3. Review manual ASR Studio behavior on a real transcript when the user is ready.
4. Remove this progress file only after the user confirms the task can be closed.
