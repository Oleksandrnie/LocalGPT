# ASR Analysis Modes Progress

## Status

In progress.

Last committed checkpoint:

- `b1f52fd UI rebuild, progress file`

Current uncommitted work after `b1f52fd`:

- Mobile/PWA chat streaming hardening:
  - dedupe repeated SSE `delta` events by per-task `sequence`;
  - keep existing partial-content replay protection for tab reload/recovery;
  - convert pagehide/manual SSE close into polling fallback instead of leaving the send flow pending;
  - ignore late SSE events after a task stream has already settled;
  - intended fix for iPhone/PWA cases where EventSource reconnects to `/chat/tasks/{id}/events` and replays old deltas, making the UI look like an endless repeated generation.
- Tailscale plugin backend-port detection hardening:
  - plugin command/status now prefer the actual FastAPI request server port from `request.scope["server"]`;
  - avoids falling back to hardcoded/default `8000` when LocalGPT selected a nearby free port such as `8001+`;
  - Tailscale Serve is still not run automatically by the app; the plugin reports the dynamic command and current Serve target status.

Current dirty files:

- `backend/apps/plugins/tailscale.py`
- `documentation/progress/asr-analysis-modes-progress.md`
- `tests/test_plugin_registry.py`
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

### `b1f52fd UI rebuild, progress file`

Committed ASR Studio UI/output pass after the user confirmed the new summary is already workable enough:

- content quality is no longer the main blocker;
- priority shifted to readable ASR UI/output formatting and layout.

User-reported summary state:

- `Умное саммари` output is useful enough for work when user knows the meeting context;
- output is not perfect, but comparable enough to cloud LLM imperfections;
- main UI problem is raw formatting artifacts and technical symbols in display;
- raw pipeline diagnostics should not pollute the main readable summary.

Implemented and committed:

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

## Current Uncommitted Mobile/PWA Chat Stream Fix

User-reported problem:

- On iPhone/mobile PWA, after opening the app, some LLM replies can appear to generate forever while repeating the same text.
- During the stuck state, UI controls appear unresponsive.
- Server log showed a single `POST /chat/tasks`, then repeated `GET /chat/tasks/{task_id}/events` for the same task before the UI reload.
- Deployment detail: the Mac is the main LocalGPT server; the iPhone reaches it through Tailscale.

Likely cause:

- Browser `EventSource` can reconnect automatically when mobile/PWA networking, Tailscale tunnel conditions, or page lifecycle interrupts SSE.
- The backend SSE route currently reads task delta artifacts from offset `0` for each new connection.
- The client already filtered replay against persisted partial message text after a full reload, but did not dedupe repeated deltas by `sequence` inside the same live tab.
- Replayed deltas could therefore be appended again, and repeated renders/typewriter backlog could make the interface feel frozen.
- The old `pagehide` handler also closed `EventSource` without rejecting the active wait promise, which could leave the PWA in an in-memory `isSending=true` state until timeout.

Implemented in uncommitted files:

- `web_ui/js/app.js` tracks the last seen delta `sequence` in `state.chatTaskReplay`.
- Repeated or already replay-covered deltas return `null` and do not trigger `renderMessages()`.
- Manual/pagehide SSE interruption now rejects the stream wait as `streamConnectionFailed`, so existing send/recover flows fall back to `/chat/tasks/{id}` polling.
- SSE event handlers now ignore late events after the stream promise has settled.

Safe verification already run for the uncommitted mobile/PWA fix:

- `node --check web_ui/js/app.js`
- `node tests/markdown_rendering.test.mjs`
- `git diff --check`

## Current Uncommitted Tailscale Port Detection Fix

User-reported concern:

- Do not hardcode Tailscale proxy target to one port.
- LocalGPT can start on `8000`, `8001`, `8002`, etc. if earlier ports are busy.
- The plugin UI/docs must dynamically reflect the active backend port.

Observed state during debug:

- LocalGPT was listening on `127.0.0.1:8001`.
- Tailscale Serve status still pointed at `http://127.0.0.1:8000`.
- Plugin UI correctly showed `Serve active for another target` and exposed `tailscale serve --bg http://127.0.0.1:8001`.

Implemented in uncommitted files:

- `backend/apps/plugins/tailscale.py` now reads the actual FastAPI server port from `request.scope["server"]` before runtime file/env/default fallback.
- Added regression coverage in `tests/test_plugin_registry.py` proving request server port wins over stale runtime file and env defaults.

Important boundary:

- The app still does not automatically run or rewrite `tailscale serve`; this is currently a deliberate safety constraint.
- Dynamic behavior means the plugin computes and displays the correct command/status from the active backend port.
- If automatic Tailscale Serve reconfiguration is desired later, treat it as an explicit security-sensitive design change.

Safe verification already run:

- `venv/bin/python -m py_compile backend/apps/plugins/tailscale.py tests/test_plugin_registry.py`
- `venv/bin/python -m unittest tests.test_plugin_registry -q`
- `node --check web_ui/js/app.js`
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

1. User-side retest on iPhone/PWA: start a streamed chat generation, background/reopen the app, and confirm the answer does not repeat old chunks.
2. Confirm Tailscale plugin UI shows the active backend port after server restarts onto `8000+`.
3. If the mobile/PWA issue persists, inspect Tailscale/iOS EventSource reconnection timing and consider a backend SSE resume offset or `Last-Event-ID` support.
4. Visually verify ASR Studio layout in browser.
5. Fix any spacing/overflow issues from the result-first layout.
6. Decide whether warnings need a visible diagnostics chip/list.
7. Keep copy/download plain text/markdown, not rendered HTML.
8. Consider adding a separate lightweight `Перевести summary` action later:
   - should translate the existing summary only;
   - must not rerun ASR, structurer, or full pipeline;
   - should store/display a language-specific summary variant if implemented.
9. Update README/technical docs if UI/output pass is accepted.
10. Add an ASR Studio checkbox/toggle to show/hide service information returned after analysis, including warning blocks like `Предупреждения: - raw_transcript_chunked:2`.
11. Run safe checks again before commit.
12. Commit current mobile/PWA and Tailscale port-detection fixes after user confirms behavior.
13. Do not remove this progress file until user confirms the whole ASR Studio task is complete.

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

- `b1f52fd UI rebuild, progress file`

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
- ASR Studio UI/output pass уже закоммичен:
  - summary/tasks рендерятся через Markdown renderer;
  - main summary view не добавляет structured/debug/raw warnings после `run.summary`;
  - ASR Studio layout переставлен в result-first схему;
  - история ASR получила отдельную кнопку удаления записи.

Что сейчас не закоммичено:

- Mobile/PWA chat stream fix:
  - `web_ui/js/app.js`;
  - `backend/apps/plugins/tailscale.py`;
  - `tests/test_plugin_registry.py`;
  - `documentation/progress/asr-analysis-modes-progress.md`.
- Клиент теперь дедуплицирует SSE `delta` по `sequence` внутри активного task replay.
- Уже покрытые replay-куски не вызывают `renderMessages()`.
- `pagehide`/ручное закрытие SSE теперь переводит ожидание генерации в polling fallback, а не оставляет PWA в подвешенном состоянии.
- Late SSE events после settled stream игнорируются.
- Контекст: Mac является основным сервером, iPhone подключается через Tailscale.
- Цель: убрать iPhone/PWA баг, где `EventSource` через Tailscale/мобильный lifecycle переподключается к `/chat/tasks/{id}/events`, backend заново отдаёт старые deltas, а UI выглядит как бесконечная повторяющаяся генерация.
- Tailscale plugin теперь берёт активный backend-port из `request.scope["server"]` перед runtime/env/default fallback, чтобы не скатываться на hardcoded/default `8000`, когда LocalGPT поднялся на `8001+`.
- Важно: приложение по-прежнему не запускает и не переписывает `tailscale serve` автоматически; plugin показывает правильную динамическую команду и статус текущего Serve target.

Что пользователь сообщил по качеству:

- Новый результат `Умное саммари` уже достаточно рабочий, чтобы с ним быстро работать.
- Главная текущая проблема не качество summary, а отображение: raw markdown symbols, технические символы и диагностика в основном выводе.

Что нужно сделать дальше:

1. Попросить пользователя проверить iPhone/PWA сценарий с обычной streamed chat генерацией.
2. Проверить, что Tailscale plugin после restart на `8000+` показывает активный порт, а не default `8000`.
3. Если повтор останется, следующим шагом смотреть Tailscale/iOS timing и backend SSE resume offset / `Last-Event-ID`.
4. Визуально проверить ASR Studio layout в браузере, не запуская ASR/LLM.
5. Исправить spacing/overflow/адаптивность, если видно проблемы.
6. Решить, как показывать warnings: лучше отдельная диагностика/chips/details, не внутри основного summary.
7. В рамках этой ветки добавить checkbox/toggle для показа/скрытия служебной информации после анализа, например блока `Предупреждения: - raw_transcript_chunked:2`; данные backend не удалять, управлять только отображением в UI.
8. Убедиться, что copy/download/send/save context используют plain markdown/text, а не HTML.
9. Запустить только безопасные проверки:
   - `node --check web_ui/js/app.js`
   - `node tests/markdown_rendering.test.mjs`
   - `git diff --check`
   - при Python-изменениях `py_compile` и generic mocked tests.
10. Обновить progress-файл.
11. После одобрения пользователя сделать коммит текущих mobile/PWA и Tailscale port-detection fixes.

Не делать:

- Не запускать реальные ASR/LLM/Ollama summary тесты.
- Не добавлять специальные словари/правила под конкретную встречу.
- Не удалять `documentation/progress/asr-analysis-modes-progress.md`.
```
