# ASR Analysis Modes Progress

## Status

In progress.

Last committed checkpoint:

- `fe154d1 Improve ASR analysis controls and thinking defaults`

Current uncommitted work after `fe154d1`:

- ASR Studio UI/result-output pass:
  - result-first ASR Studio layout;
  - formatted Markdown rendering for ASR summary/tasks output;
  - per-record delete button in ASR history;
  - progress file refresh.

Current dirty files:

- `documentation/progress/asr-analysis-modes-progress.md`
- `web_ui/css/style.css`
- `web_ui/gui_html.html`
- `web_ui/js/app.js`

Do not delete this progress file until the full ASR Studio task is complete and the user explicitly confirms it can be closed.

## Hard Constraints

- Do not run live ASR, live LLM, live summary, Ollama-heavy, or full pipeline tests without explicit user permission.
- The user manually runs real ASR/summary tests and monitors Mac temperature.
- Only safe checks are allowed by default:
  - `venv/bin/python -m py_compile ...`
  - `node --check web_ui/js/app.js`
  - `node tests/markdown_rendering.test.mjs`
  - generic mocked/unit tests
  - `git diff --check`
- Do not add meeting-specific runtime rules, tests, dictionaries, replacements, or hardcoded business/domain context.
- Do not hardcode domains, subdomains, companies, marketplaces, email files, names, concrete meeting terms, or transcript-specific corrections.
- Summary quality fixes must be generic and evidence-based.
- User settings have priority over analysis modes. If a stage is `enabled=false`, the backend must not silently re-enable it.

## Core Goal

Make ASR Studio usable for long meeting transcripts without returning to heavy default processing:

- normal mode should avoid overheating the Mac;
- `Умное саммари` should produce a useful semantic summary from raw transcript/chunks through structurer -> summary;
- repeated spoken emphasis must be treated as an importance signal, not as noise;
- full analysis must remain gated and hard to launch accidentally;
- ASR result should be readable in UI, without raw Markdown artifacts or technical pipeline noise in the main summary view.

## Important Architecture Decisions

- Cleaner stays in the project but is not part of default summary routes.
- Cleaner is a manual/optional stage because it can remove repeated emphasis and speech details.
- ASR modes are recommendations, not hard dependencies.
- Stage setting `Не использовать` means `enabled=false`; backend must respect it in every route.
- `summary` action means fast summary: raw transcript -> summary.
- `smart_summary` means recommended smart summary: raw transcript/chunks -> structurer -> summary.
- `full` means heavy full analysis: raw transcript/chunks -> segmenter -> speaker resolver -> structurer -> summary.
- Full analysis is gated by profile setting `asr_full_analysis_enabled=false` by default.
- ASR pipeline settings are isolated from chat model settings under service model key `__asr_pipeline__`.
- Chat and ASR share the same model store/catalog, but do not share runtime settings.
- ASR LLM stages default to `think:false` for Ollama thinking-capable models.
- Chat topbar `Thinking` affects only selected chat model settings.
- ASR `Thinking LLM стадий` affects only ASR pipeline settings.

## Committed Work

### `dcd43ec Stabilize ASR Studio pipeline defaults`

Earlier checkpoint that stabilized ASR Studio defaults and chunk/merge behavior.

### `b3ab74d Add ASR analysis context controls`

Added profile-level ASR analysis context:

- stored `asr.analysis_prompt` in profile preferences;
- exposed `Контекст анализа` in ASR settings;
- wired it through UI/API/backend;
- included it in structurer/summary/retry prompts;
- added generic repeated-emphasis instruction:
  - if an important point repeats in different words, treat repetition as importance evidence, not noise.

### `bd67e59 Add ASR analysis modes and grounded summaries`

Implemented major ASR behavior:

- ASR Studio `Режим анализа` selector;
- one primary `Запустить анализ` button;
- backend `smart_summary` action;
- `summary` mapped to fast raw transcript -> summary;
- `smart_summary` mapped to structurer -> summary without cleaner and without speaker resolver;
- `full` mapped to segmenter -> speaker resolver -> structurer -> summary;
- full analysis gated by `Разрешить полный анализ`;
- stage `Не использовать` support in UI/backend;
- profile-level output language selection:
  - `auto`;
  - `ru`;
  - `en`;
- summary language follows transcript by default and can be manually forced;
- generic grounding validation for fabricated/instruction-echo outputs;
- generic format/quality validation for weak dialogue overview outputs;
- structured-evidence fallback for smart/full when summary validation fails;
- generic tests only, no meeting-specific content.

### `fe154d1 Improve ASR analysis controls and thinking defaults`

Implemented ASR/runtime load-control and thinking settings:

- dedicated ASR pipeline settings model key `__asr_pipeline__`;
- default summary model changed to `qwen3:8b` to avoid loading two large models for common smart summary;
- ASR diagnostics toggle:
  - when enabled, creates profile diagnostics folder;
  - when disabled, removes it;
- emergency ASR stop fallback:
  - `/asr/stop` unloads active/default ASR pipeline models;
  - if Ollama runner remains stuck, helper can terminate stuck runner PIDs;
- Apple Silicon ASR pipeline default prefers explicit Metal offload via high `OLLAMA_PIPELINE_NUM_GPU` default;
- ASR LLM calls disable silent CPU fallback when Metal fails;
- native Ollama runtime accepts per-request top-level `think`;
- chat model settings persist `ollama_think`;
- topbar `Thinking` dropdown added for chat models:
  - button text stays `Thinking`;
  - dropdown has `Включено` / `Выключено`;
  - enabled state is shown by subtle purple glow;
- ASR settings expose `Thinking LLM стадий`:
  - `Выключено`;
  - `Включено`;
  - `Авто Ollama`;
- ASR default is thinking off:
  - if ASR does not explicitly override `ollama_think`, backend effective setting is `off`;
  - ASR `_call_stage` sends `think:false`;
- missing required summary heading is repaired locally:
  - if usable summary body lacks `## Краткое резюме` / `## Brief Summary`, backend prepends heading;
  - missing heading alone no longer triggers a second LLM call or 502.

Safe verification before `fe154d1`:

- `venv/bin/python -m py_compile app/config.py app/db.py app/routes/profiles.py app/schemas/core.py backend/apps/chat/service.py backend/apps/chat/routes.py backend/apps/chat/services/ollama_runtime.py backend/apps/asr/pipeline.py tests/test_model_router.py tests/test_pipeline_memory.py`
- `node --check web_ui/js/app.js`
- `git diff --check`
- `venv/bin/python -m unittest tests.test_model_router tests.test_pipeline_memory`
- 111 mocked/unit tests passed.

## Current Uncommitted UI/Output Pass

Started after user confirmed the new summary is already workable enough:

- content quality is no longer the main blocker;
- current priority is readable ASR UI/output formatting and layout.

User-reported summary state:

- `Умное саммари` output is useful enough for work when user knows the meeting context;
- output is not perfect, but comparable enough to cloud LLM imperfections;
- main UI problem is raw formatting artifacts and technical symbols in display;
- raw pipeline diagnostics should not pollute the main readable summary.

Implemented in uncommitted files:

- ASR summary/tasks output now renders through shared Markdown renderer instead of raw `<pre>` text.
- Markdown artifacts such as `##`, `**bold**`, bullets and inline code should display as formatted UI.
- Main summary view now returns `run.summary` directly when summary exists.
- Main summary view no longer appends structured fallback/debug sections after an existing summary.
- Main summary view no longer appends raw warnings like `raw_transcript_chunked:2` after an existing summary.
- Copy/download behavior still uses plain markdown/text source through `getAsrToolSelectedContent()`.
- ASR Studio layout moved toward the user sketch:
  - left: search, selected file card, result area, tabs, action buttons, pipeline route;
  - middle: file/settings/language controls and analysis mode selector;
  - right: transcript history database;
- ASR history list now renders each record as an item with:
  - main clickable content area;
  - separate delete button `×`;
- Search behavior:
  - on text tab, search selects text inside textarea;
  - on result tabs, search reports whether current rendered result contains the query.

Safe verification already run for the uncommitted UI/output pass:

- `node --check web_ui/js/app.js`
- `node tests/markdown_rendering.test.mjs`
- `git diff --check`

## Known UI Follow-Ups

Needs user-side visual review in ASR Studio:

- check that the result-first layout matches the screenshot intent at fullscreen size;
- check that middle control column width feels right;
- check that right history column remains readable;
- check that per-record delete button is not too visually noisy;
- check that Markdown summary output is readable and not too large;
- check mobile/responsive behavior if ASR Studio is opened on narrow width;
- verify that `Открыть анализ`, copy/download, save context, send to chat still use expected text.

Possible next refinement:

- show technical warnings in a separate compact diagnostics/details area instead of inside summary;
- convert technical warnings into human-readable UI text:
  - `raw_transcript_chunked:2` -> `Transcript обработан в 2 чанка`;
  - `summary_required_heading_added` -> `Заголовок summary добавлен автоматически`;
- add collapsible `Диагностика` near pipeline route;
- keep diagnostics separate from copy/download unless explicitly requested.
- backlog for this branch/task: add an ASR Studio checkbox/toggle that controls whether service/model technical information is shown after analysis, for example:
  - hidden by default in the readable summary view;
  - visible when enabled by the user;
  - covers service blocks such as `Предупреждения: - raw_transcript_chunked:2`;
  - should not remove warnings from backend data, only hide/show them in UI.

## Current Pending Tasks

1. Visually verify ASR Studio layout in browser.
2. Fix any spacing/overflow issues from the result-first layout.
3. Decide whether warnings need a visible diagnostics chip/list.
4. Keep copy/download plain text/markdown, not rendered HTML.
5. Consider adding a separate lightweight `Перевести summary` action later:
   - should translate the existing summary only;
   - must not rerun ASR, structurer, or full pipeline;
   - should store/display a language-specific summary variant if implemented.
6. Update README/technical docs if UI/output pass is accepted.
7. Add an ASR Studio checkbox/toggle to show/hide service information returned after analysis, including warning blocks like `Предупреждения: - raw_transcript_chunked:2`.
8. Run safe checks again before commit.
9. Commit UI/output pass when user approves.
10. Do not remove this progress file until user confirms the whole ASR Studio task is complete.

## Tests And Safe Checks To Prefer

Allowed by default:

- `node --check web_ui/js/app.js`
- `node tests/markdown_rendering.test.mjs`
- `git diff --check`
- `venv/bin/python -m py_compile ...` for changed Python files if any
- generic mocked/unit tests

Do not run without explicit user permission:

- live ASR transcription;
- live summary generation;
- Ollama-heavy tests;
- long transcript/full pipeline tests;
- anything that loads local LLMs for generation.

## Handoff Prompt For New Chat

Use this prompt if continuing in another chat. Do not include a hardcoded project path; first locate/open the LocalGPT workspace on the current computer.

```text
Продолжаем работу в проекте LocalGPT, ветка bug_fix/asr-studio.

Главные ограничения:

- Не запускать live ASR / live LLM / live summary / full pipeline тесты без явного разрешения пользователя.
- Пользователь сам запускает реальные ASR/summary проверки и следит за температурой Mac.
- Не добавлять meeting-specific контент, словари, regex/fixups или тесты под конкретную встречу.
- Не хардкодить домены, поддомены, маркетплейсы, YML, email-файлы, имена, бизнес-контекст или специальные правила под один transcript.
- Все улучшения summary должны быть универсальными.
- User settings имеют абсолютный приоритет над режимом анализа: если stage `enabled=false`, backend не должен запускать эту стадию ни в каком режиме.
- Progress-файл `documentation/progress/asr-analysis-modes-progress.md` нужно актуализировать по ходу работы и не удалять до полного завершения и подтверждения пользователя.

Последний коммит:

- `fe154d1 Improve ASR analysis controls and thinking defaults`

Что уже реализовано и закоммичено:

- ASR Studio получил selector `Режим анализа`:
  - `Быстрое саммари`: raw transcript -> summary;
  - `Умное саммари`: raw transcript/chunks -> structurer -> summary;
  - `Полный анализ`: segmenter -> speaker resolver -> structurer -> summary, доступен только после включения `Разрешить полный анализ`.
- Cleaner не входит в обычные режимы по умолчанию; он ручной/опциональный.
- В настройках стадий есть `Не использовать`; backend уважает `enabled=false`.
- Добавлен profile-level `Контекст анализа`.
- Добавлен `Язык результата`: auto/ru/en.
- Summary language по умолчанию должен следовать языку transcript, но может быть выбран вручную.
- Добавлена generic логика, что повтор важной мысли разными словами является сигналом важности.
- Добавлена grounding/format validation для summary, чтобы не сохранять fabricated/instruction-echo/generic overview ответы.
- Если summary без обязательного `## Краткое резюме` / `## Brief Summary`, backend добавляет заголовок локально и не гоняет второй LLM call только из-за этого.
- ASR pipeline settings отделены от chat model settings под `__asr_pipeline__`.
- ASR default thinking выключен: ASR LLM stages отправляют `think:false`, если пользователь явно не переопределил настройку.
- Chat topbar `Thinking` влияет только на chat model settings.
- ASR `Thinking LLM стадий` влияет только на ASR pipeline settings.
- ASR stop умеет выгружать/останавливать stuck Ollama runners.

Что сейчас не закоммичено:

- UI/output pass для ASR Studio:
  - `web_ui/gui_html.html`
  - `web_ui/css/style.css`
  - `web_ui/js/app.js`
  - `documentation/progress/asr-analysis-modes-progress.md`
- ASR summary/tasks output теперь рендерится через общий Markdown renderer вместо raw `<pre>`.
- Main summary view больше не добавляет structured/debug sections и raw warnings после `run.summary`.
- ASR Studio layout переставлен по sketch пользователя:
  - слева поиск/результат/табы/кнопки/pipeline route;
  - по центру file/settings/language controls и выбор режима анализа;
  - справа база транскрибаций.
- В истории ASR у каждой записи добавлена отдельная кнопка удаления.

Что пользователь сообщил по качеству:

- Новый результат `Умное саммари` уже достаточно рабочий, чтобы с ним быстро работать.
- Главная текущая проблема не качество summary, а отображение: raw markdown symbols, технические символы и диагностика в основном выводе.

Что нужно сделать дальше:

1. Открыть текущий diff и проверить незакоммиченный UI/output pass.
2. Визуально проверить ASR Studio layout в браузере, не запуская ASR/LLM.
3. Исправить spacing/overflow/адаптивность, если видно проблемы.
4. Решить, как показывать warnings: лучше отдельная диагностика/chips/details, не внутри основного summary.
5. В рамках этой ветки добавить checkbox/toggle для показа/скрытия служебной информации после анализа, например блока `Предупреждения: - raw_transcript_chunked:2`; данные backend не удалять, управлять только отображением в UI.
6. Убедиться, что copy/download/send/save context используют plain markdown/text, а не HTML.
7. Запустить только безопасные проверки:
   - `node --check web_ui/js/app.js`
   - `node tests/markdown_rendering.test.mjs`
   - `git diff --check`
   - при Python-изменениях `py_compile` и generic mocked tests.
8. Обновить progress-файл.
9. После одобрения пользователя сделать коммит UI/output pass.

Не делать:

- Не запускать реальные ASR/LLM/Ollama summary тесты.
- Не добавлять специальные словари/правила под конкретную встречу.
- Не удалять `documentation/progress/asr-analysis-modes-progress.md`.
```
