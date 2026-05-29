# ASR Analysis Modes Progress

## Status

In progress.

Last committed checkpoint:

- `2bc8e60 Harden mobile streaming and Tailscale port detection`

Current uncommitted work after `2bc8e60`:

- ASR Studio UX pass (2026-05-29):
  - ASR Studio now opens immediately in fullscreen mode by default;
  - backend/profile plumbing:
    - added profile-level runtime flag `show_router_thinking_toggle` with default `false`;
    - profile settings normalization now accepts and persists `show_router_thinking_toggle`;
    - transcript names are normalized and truncated to `120` chars on create/update to avoid oversized auto-generated titles in ASR history.
  - transcript database behavior updated:
    - mobile: database moved to the top, with `Less/More` collapse behavior for compact UX;
    - mobile: selecting a transcript auto-collapses the database list;
    - desktop: transcript database now opens as an overlay sidebar above content (does not reflow core columns);
    - desktop: selecting a transcript auto-collapses the overlay sidebar;
  - analysis panel refinements:
    - removed internal panel scrolling for the compact "Анализ" block;
    - moved descriptive analysis-mode text under `?` tooltip;
    - analysis mode selector kept as an explicit dropdown control.
  - mobile topbar controls:
    - added quick chat-model picker in the top-right icon menu;
    - placed model picker before the mobile `Thinking` button;
    - mobile `Thinking` control uses icon-only trigger and dropdown;
    - desktop topbar quick model select was replaced with the same dropdown picker pattern as mobile;
    - mobile model dropdown now shows only model names (no extra metadata text in list items);
    - mobile model dropdown dimensions constrained (`max-content` + viewport max width/height) to avoid overflow outside screen;
    - unified chat model picker and `Thinking`: separate visible `Thinking` button is hidden, and thinking-capable selected models now show a thin Apple-style switch inside the model dropdown;
    - all thinking-capable chat models now show the switch immediately in the dropdown, even when not selected; non-selected models render it in `off` state, and toggling it first switches to that model and then saves `Thinking`;
    - reusable thin Apple-style checkbox/switch styling applied to all checkbox inputs with LocalGPT purple checked state and sliding knob animation;
    - switch knob vertically centered and quick model dropdown/switch colors adapted for both dark and light themes;
    - model picker now renders immediately on app startup; before models are loaded it stays visible but disabled;
    - Auto / Smart Router no longer shows Thinking in the main picker by default; LLM settings now include a dedicated checkbox to reveal or hide router Thinking there;
    - hidden mobile chat title and adjusted sidebar-open icon to vertical `|||` bars.
- ASR transcript DB history entries:
  - added right-click context action `Переименовать`;
  - selection auto-collapses history on mobile and desktop overlay mode.
- TTS Studio mobile history behavior:
  - moved history block to top (same UX pattern as ASR);
  - added `More/Less` collapse toggle;
  - selecting history item auto-collapses;
  - opening TTS Studio now always starts with collapsed (`Less`) state.

Safe verification for the current uncommitted work:

- `node --check web_ui/js/app.js`
- `python3 -m py_compile app/config.py app/routes/profiles.py`
- `git diff --check`

- UI update finalized (desktop + mobile):
  - desktop ASR Studio aligned to target layout (left collapsible transcript DB sidebar, center results, right controls);
  - tabs moved above the result area;
  - main transcript/result field stretches to bottom and is non-resizable;
  - added persistent reopen control for collapsed DB sidebar (no page reload needed);
  - mobile layout kept single-column with compact controls and bottom actions.

- ASR `Сохранить в контекст` now creates a linked RAG source:
  - the ASR context is still stored as a transcript with `labels.origin=asr_context`;
  - backend auto-indexes it into RAG as source type `asr_context`;
  - the RAG panel lists saved ASR contexts separately from files;
  - deleting the context from RAG also deletes the linked transcript/context record;
  - saving context auto-enables RAG for the active profile if it was off and shows an indexed/chunks notification.
- ASR Studio bottom action row is simplified to the requested primary actions:
  - `Копировать`;
  - `Сохранить в контекст`;
  - `Скачать TXT`;
  - `Добавить к промпту`.
- ASR desktop layout pass (variant 2 in progress):
  - transcript database moved into the main left column (`asr-history-column`) instead of separate outer sidebar;
  - center content remains the largest area for text/summary/tasks/roles;
  - right controls grouped into a compact vertical panel with top action row (`Настройки`, `Обновить`, `Остановить`);
  - mobile fallback keeps single-column order: content -> controls -> history.
- ASR pipeline reset defaults now match the requested stage table:
  - `cleaner`: disabled, temp `0`, max tokens `6000`;
  - `segmenter`: disabled, temp `0.05`, max tokens `6000`;
  - `speaker_resolver`: disabled, temp `0`, max tokens `3000`;
  - `structurer`: `qwen3:8b`, temp `0.05`, max tokens `6000`;
  - `summary`: `qwen3:8b`, temp `0.05`, max tokens `7000`.
  - reset explicitly writes these ASR pipeline defaults so stale profile-level pipeline settings cannot override them.
- Model residency policy is tightened:
  - manual non-router model selection keeps the model alive for at least `5m`;
  - router keep-alive remains separate;
  - only one target model is kept resident;
  - selecting another target model unloads the previous target instead of keeping two side by side.

Current dirty files:

- `app/config.py`
- `app/db.py`
- `app/routes/profiles.py`
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

Safe verification before `b1f52fd`:

- `node --check web_ui/js/app.js`
- `node tests/markdown_rendering.test.mjs`
- `git diff --check`

### `2bc8e60 Harden mobile streaming and Tailscale port detection`

Committed mobile/PWA chat stream hardening and dynamic Tailscale target detection.

Mobile/PWA user-reported problem:

- On iPhone/mobile PWA, after opening the app, some LLM replies can appear to generate forever while repeating the same text.
- During the stuck state, UI controls appear unresponsive.
- Server log showed a single `POST /chat/tasks`, then repeated `GET /chat/tasks/{task_id}/events` for the same task before the UI reload.
- Deployment detail: the Mac is the main LocalGPT server; the iPhone reaches it through Tailscale.

Mobile/PWA likely cause:

- Browser `EventSource` can reconnect automatically when mobile/PWA networking, Tailscale tunnel conditions, or page lifecycle interrupts SSE.
- The backend SSE route currently reads task delta artifacts from offset `0` for each new connection.
- The client already filtered replay against persisted partial message text after a full reload, but did not dedupe repeated deltas by `sequence` inside the same live tab.
- Replayed deltas could therefore be appended again, and repeated renders/typewriter backlog could make the interface feel frozen.
- The old `pagehide` handler also closed `EventSource` without rejecting the active wait promise, which could leave the PWA in an in-memory `isSending=true` state until timeout.

Implemented and committed:

- `web_ui/js/app.js` tracks the last seen delta `sequence` in `state.chatTaskReplay`.
- Repeated or already replay-covered deltas return `null` and do not trigger `renderMessages()`.
- Manual/pagehide SSE interruption now rejects the stream wait as `streamConnectionFailed`, so existing send/recover flows fall back to `/chat/tasks/{id}` polling.
- SSE event handlers now ignore late events after the stream promise has settled.

Tailscale user-reported concern:

- Do not hardcode Tailscale proxy target to one port.
- LocalGPT can start on `8000`, `8001`, `8002`, etc. if earlier ports are busy.
- The plugin UI/docs must dynamically reflect the active backend port.

Observed during debug:

- LocalGPT was listening on `127.0.0.1:8001`.
- Tailscale Serve status still pointed at `http://127.0.0.1:8000`.
- Plugin UI correctly showed `Serve active for another target` and exposed `tailscale serve --bg http://127.0.0.1:8001`.

Implemented and committed:

- `backend/apps/plugins/tailscale.py` reads the actual FastAPI server port from `request.scope["server"]` before runtime file/env/default fallback.
- Regression coverage in `tests/test_plugin_registry.py` proves request server port wins over stale runtime file and env defaults.

Important boundary:

- The app still does not automatically run or rewrite `tailscale serve`; this is a deliberate safety constraint.
- Dynamic behavior means the plugin computes and displays the correct command/status from the active backend port.
- If automatic Tailscale Serve reconfiguration is desired later, treat it as an explicit security-sensitive design change.

Safe verification before `2bc8e60`:

- `venv/bin/python -m py_compile backend/apps/plugins/tailscale.py tests/test_plugin_registry.py`
- `venv/bin/python -m unittest tests.test_plugin_registry -q`
- `node --check web_ui/js/app.js`
- `node tests/markdown_rendering.test.mjs`
- `git diff --check`

## Current Uncommitted ASR Context And RAG Work

User questions being addressed:

- Where does `Сохранить как контекст` save the result?
- How can the user see that the context was saved?
- How can the user remove it?
- Do models actually read the saved context?

Current behavior before this pass:

- `Сохранить как контекст` created a `transcripts` row with `labels.origin=asr_context`.
- The latest context could be picked up by chat through the session transcript path.
- It was not visible as a first-class RAG item.
- It was not automatically indexed into RAG.
- Deletion status was not obvious to the user.

Implemented in current uncommitted files:

- `backend/apps/rag/service.py` adds `asr_context` as a source document type.
- ASR contexts are indexed with local hash embeddings and chunk metadata, same search path as manual RAG files.
- `backend/apps/asr/transcripts.py` auto-indexes transcripts whose `labels.origin` is `asr_context`.
- Deleting an ASR context transcript removes the linked RAG source.
- `DELETE /rag/contexts` removes the RAG context and linked transcript/context record.
- `rag_service.status(profile_id)` now returns `contexts` for UI display.
- RAG panel shows context count and a separate `Контекст` section above file sources.
- Saving ASR context auto-enables RAG for the active profile if it was off.
- UI status/footer now reports that the context was saved, indexed, and how many chunks were created when available.
- New regression test verifies:
  - ASR context transcript auto-indexes into RAG;
  - RAG search finds the saved ASR fact;
  - RAG status lists the context;
  - deleting from RAG removes both the source and transcript.

## Current Uncommitted ASR Studio Actions Work

User direction:

- Reduce the ASR action row; the previous set had too many overlapping actions.
- Keep the useful user-facing actions:
  - copy text;
  - save to context;
  - download txt;
  - add to prompt.
- Do not keep delete-record as a bottom-row action; deletion belongs in the transcript/history database.

Implemented in current uncommitted files:

- ASR bottom action row now shows:
  - `Копировать`;
  - `Сохранить в контекст`;
  - `Скачать TXT`;
  - `Добавить к промпту`.
- Removed visible bottom-row buttons for:
  - clean;
  - save edits;
  - send to chat;
  - clear editor;
  - delete record;
  - clear history;
  - open analysis.
- Existing optional JS handlers remain tolerant of absent buttons.

## Current Uncommitted Model Residency Work

User direction:

- Manual model choice should keep the model in memory for at least 5 minutes.
- This applies to all model types except router.
- Router remains a separate story.
- If the user switches models again, the previous target model should unload.
- Do not keep two target models resident side by side.

Implemented in current uncommitted files:

- `ollama_manual_keep_alive` default is now `5m`.
- UI residency defaults now show manual keep-alive as `5m`.
- `resolve_model_keep_alive(..., mode="manual")` clamps non-router keep-alive to at least `5m`, even if explicit manual payload is shorter.
- Router keep-alive remains separately configurable and is not clamped by this manual target rule.
- Target residency limit is effectively one active target model.
- The resident-model help tooltip now describes:
  - max target models: `1`;
  - manual selection unloads the previous target;
  - manual keep-alive minimum: `5m`;
  - router is outside target-model limit.

Safe verification already run for the current uncommitted pass:

- `venv/bin/python -m py_compile app/config.py app/routes/profiles.py backend/apps/chat/services/model_residency.py tests/test_model_router.py backend/apps/rag/service.py backend/apps/rag/routes.py backend/apps/asr/transcripts.py tests/test_pipeline_memory.py`
- `venv/bin/python -m unittest tests.test_model_router -q`
- `venv/bin/python -m unittest tests.test_pipeline_memory.LocalGPTPipelineMemoryTestCase.test_asr_context_transcript_auto_indexes_rag_and_can_be_deleted_from_rag -q`
- `venv/bin/python -m unittest tests.test_pipeline_memory.LocalGPTPipelineMemoryTestCase.test_asr_pipeline_reset_uses_current_defaults_over_stale_profile_pipeline tests.test_pipeline_memory.LocalGPTPipelineMemoryTestCase.test_default_pipeline_uses_current_catalog_and_token_budget tests.test_pipeline_memory.LocalGPTPipelineMemoryTestCase.test_asr_pipeline_defaults_disable_ollama_thinking -q`
- `node --check web_ui/js/app.js`
- `node tests/markdown_rendering.test.mjs`
- `git diff --check`

Local UI smoke check on `http://127.0.0.1:8000/ui/gui_html.html`:

- ASR action row shows only:
  - `Копировать`;
  - `Сохранить в контекст`;
  - `Скачать TXT`;
  - `Добавить к промпту`.
- Removed old action button IDs are absent from DOM:
  - `asrToolCleanButton`;
  - `asrToolSaveButton`;
  - `asrToolSendButton`;
  - `asrToolClearButton`;
  - `asrToolDeleteButton`;
  - `asrToolClearHistoryButton`;
  - `asrToolOpenAnalysisButton`.
- RAG panel opens and displays context count in status.
- Current real profile had `контекстов: 0`, so no live user-data context was created for visual testing.
- Residency tooltip says max target models `1`, manual selection unloads previous target, and manual keep-alive minimum is 5 minutes.

## Known UI Follow-Ups

Needs user-side visual review in ASR Studio:

- check that the result-first layout matches the screenshot intent at fullscreen size;
- check that middle control column width feels right;
- check that right history column remains readable;
- check that per-record delete button is not too visually noisy;
- check that Markdown summary output is readable and not too large;
- check mobile/responsive behavior if ASR Studio is opened on narrow width;
- verify that `Копировать`, `Сохранить в контекст`, `Скачать TXT`, and `Добавить к промпту` use expected text.

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

1. Visually verify RAG panel after saving an ASR context:
   - context appears in a separate `Контекст` section;
   - delete button removes it from RAG and linked transcript/context storage;
   - context count updates.
2. Confirm saved ASR context is injected into model prompts through RAG when RAG is enabled.
3. Confirm manual model switching unloads the previous target model and keeps the new non-router target alive for at least `5m` in a real app session if needed.
4. Run safe checks again after any visual/UI fixes.
5. Commit the current ASR context/RAG, ASR actions, residency, and progress update pass.
6. User-side retest on iPhone/PWA remains useful:
   - start a streamed chat generation;
   - background/reopen the app;
   - confirm the answer does not repeat old chunks.
7. Confirm Tailscale plugin UI still shows the active backend port after server restarts onto `8000+`.
8. If the mobile/PWA issue persists, inspect Tailscale/iOS EventSource reconnection timing and consider a backend SSE resume offset or `Last-Event-ID` support.
9. Continue ASR Studio visual review:
   - result-first layout at fullscreen size;
   - middle control column width;
   - right history column readability;
   - Markdown summary output readability;
   - mobile/responsive behavior.
10. Decide whether warnings need a visible diagnostics chip/list.
11. Keep copy/download plain text/markdown, not rendered HTML.
12. Consider adding a separate lightweight `Перевести summary` action later:
   - should translate the existing summary only;
   - must not rerun ASR, structurer, or full pipeline;
   - should store/display a language-specific summary variant if implemented.
13. Update README/technical docs if UI/output/RAG-context pass is accepted.
14. Add an ASR Studio checkbox/toggle to show/hide service information returned after analysis, including warning blocks like `Предупреждения: - raw_transcript_chunked:2`.
15. Do not remove this progress file until user confirms the whole ASR Studio task is complete.

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

- `2bc8e60 Harden mobile streaming and Tailscale port detection`

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
- Mobile/PWA chat stream hardening уже закоммичен:
  - клиент дедуплицирует SSE `delta` по `sequence`;
  - pagehide/manual SSE close переводит ожидание генерации в polling fallback;
  - late SSE events после settled stream игнорируются.
- Tailscale plugin port detection уже закоммичен:
  - backend port берётся из `request.scope["server"]` перед runtime/env/default fallback;
  - plugin показывает динамическую команду для активного `8000+` порта;
  - приложение не запускает и не переписывает `tailscale serve` автоматически.

Что сейчас не закоммичено:

- ASR context/RAG pass:
  - `Сохранить в контекст` создаёт transcript с `labels.origin=asr_context`;
  - backend автоматически индексирует его в RAG source type `asr_context`;
  - RAG status возвращает `contexts`;
  - RAG panel показывает отдельную секцию `Контекст`;
  - удаление из RAG удаляет связанный transcript/context record;
  - сохранение ASR context включает RAG для активного профиля, если он был выключен, и показывает статус индексации/chunks.
- ASR Studio actions pass:
  - в нижнем action row оставлены `Копировать`, `Сохранить в контекст`, `Скачать TXT`, `Добавить к промпту`;
  - удаление записи остаётся в истории/базе транскрибаций, не в основном action row.
- ASR pipeline reset/defaults pass:
  - reset for `__asr_pipeline__` explicitly persists current `DEFAULT_PIPELINE` and `ollama_think=off`;
  - this fixes stale profile-level `settings.pipeline` overriding the new defaults after server restart;
  - UI recommendations are short:
    - disabled stages show only `Стадия выключена.`;
    - enabled stages show only the requested model recommendation text.
- Model residency pass:
  - manual non-router model keep_alive минимум `5m`;
  - router остаётся отдельным;
  - одновременно держим только одну target model;
  - при выборе новой target model старая выгружается.
- Изменённые файлы:
  - `app/config.py`;
  - `app/routes/profiles.py`;
  - `backend/apps/asr/transcripts.py`;
  - `backend/apps/chat/services/model_residency.py`;
  - `backend/apps/rag/routes.py`;
  - `backend/apps/rag/service.py`;
  - `tests/test_model_router.py`;
  - `tests/test_pipeline_memory.py`;
  - `web_ui/css/style.css`;
  - `web_ui/gui_html.html`;
  - `web_ui/js/app.js`;
  - `documentation/progress/asr-analysis-modes-progress.md`.

Что пользователь сообщил по качеству:

- Новый результат `Умное саммари` уже достаточно рабочий, чтобы с ним быстро работать.
- Главная текущая проблема не качество summary, а отображение: raw markdown symbols, технические символы и диагностика в основном выводе.

Что нужно сделать дальше:

1. Визуально проверить сохранение ASR context:
   - появляется в RAG section `Контекст`;
   - удаление из RAG удаляет linked transcript/context;
   - статус/chunk count понятен пользователю.
2. Проверить, что RAG context реально попадает в chat retrieval path при включённом RAG.
3. Визуально проверить ASR Studio action row и адаптивность, не запуская ASR/LLM.
4. Проверить manual model switching: новая target model выгружает предыдущую, keep_alive минимум `5m`; router отдельно.
5. Запустить только безопасные проверки:
   - `node --check web_ui/js/app.js`
   - `git diff --check`
   - при Python-изменениях `py_compile` и generic mocked tests.
6. Обновить progress-файл после визуальной проверки.
7. Сделать коммит текущего ASR context/RAG, ASR actions, model residency pass.
8. Попросить пользователя по возможности отдельно ретестнуть iPhone/PWA stream и Tailscale active port после серверных restart.

Не делать:

- Не запускать реальные ASR/LLM/Ollama summary тесты.
- Не добавлять специальные словари/правила под конкретную встречу.
- Не удалять `documentation/progress/asr-analysis-modes-progress.md`.
```
