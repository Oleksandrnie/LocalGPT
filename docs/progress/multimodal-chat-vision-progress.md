# Multimodal Chat Attachments and Local Vision Pipeline

## Original Task
- Goal: Реализовать ТЗ `LocalGPT_Multimodal_Chat_Vision_TZ_v1.docx`: встроенные image attachments в обычном чате, локальное хранение/preprocessing, direct Ollama vision route, явный fallback, OCR assist, persisted lifecycle, settings/cache cleanup и text-only RAG export.
- Acceptance criteria: Выполнить раздел 16 Definition of Done исходного ТЗ; поддержать PNG/JPEG/WebP, paste/drop/picker, backend-owned лимит 1–10, profile/session/message/task ownership, refresh/cancel/cleanup, отсутствие binary image ingest в RAG и безопасные mocked/static/UI проверки.
- Source ТЗ or request: `/Users/oleksandrniemchenko/Downloads/LocalGPT_Multimodal_Chat_Vision_TZ_v1.docx`; запрос пользователя от 2026-07-27 «берем в работу».

## Task Analysis
- Architecture scope: Chat-owned feature в `backend/apps/chat/`; shared SQLite/preferences остаются в `app/db.py` и `app/routes/profiles.py`; активный UI — `web_ui/gui_html.html` + `web_ui/js/app.js`; Ollama boundary — `backend/apps/chat/services/ollama_runtime.py`; RAG и OCR используются только через существующие feature boundaries.
- Affected areas/files: chat schemas/routes/tasks/services, SQLite schema/repositories, model metadata/capabilities, profile/delete/reset flows, OCR adapter, RAG explicit context source, active Web UI HTML/JS/CSS, tests и affected docs.
- Constraints and risks: Не исполнять heavy/live vision автоматически; не ломать OCR Studio; не писать binary/base64/секреты в SQLite message text/logs; ограничить v1 изображениями; сохранить profile isolation; не импортировать `compare-branch/`; существующий `docs/progress/asr-analysis-modes-progress.md` не изменять.
- Verified current state: Ветка `Multimodal_Chat_Vision`, исходное дерево чистое; `POST /chat/tasks` создаёт persisted user/assistant messages и process-local task с SSE; Ollama использует `/api/chat`; текущий chat drop для image открывает OCR; Pillow отсутствует в `venv` и должен стать явной dependency.
- Decisions: Локальные инструкции проекта переопределяют общий skill: progress path — `docs/progress/`; persistent completed-task index — `docs/CHANGELOG.md`, без дублирующего `documentation/change-index.md`.

## Documentation Impact Review
- Outcome: Required
- Documents to update: `docs/ARCHITECTURE.md` — image flow/storage/RAG boundary; `docs/knowledge/backend.md` — routes/schema/lifecycle; `docs/knowledge/providers.md` — vision capability/runtime; `docs/knowledge/ui.md` — composer/status/settings/accessibility; `docs/knowledge/rag.md` — explicit `vision_context` text source и запрет binary ingest; `docs/TESTING.md` — suites/manual/live smoke policy; `docs/CHANGELOG.md` — краткая запись завершённой функции. `README.md` и `AGENTS.md` не планируются: запуск и agent workflow не меняются.

## Implementation Stages

### Stage 1 — Contract, Data Model and Storage
- Goal: Зафиксировать schemas, settings, DB lifecycle, безопасное локальное хранение/preprocessing и HTTP contract без model integration.
- Related files: `app/schemas/`, `app/db.py`, `app/config.py`, `app/routes/profiles.py`, `backend/apps/chat/attachments.py`, `backend/apps/chat/services/attachment_storage.py`, `backend/apps/chat/services/image_preprocessing.py`, delete/reset flows, `tests/test_chat_attachments.py`, `app/requirements.txt`.
- [x] Completed: ТЗ, обязательная документация и текущие entry points проверены; DOCX отрендерен и просмотрен (17 страниц).
- [x] Completed: Contract/storage foundation, API tests and compatible model-router regression.
- [x] Completed: Checkpoint commit.
- Architectural decisions: Binary files хранятся project-scoped под `app/data/chat_attachments/profile-*`; DB хранит только backend-owned относительные paths/metadata; Pillow используется для decode/orientation/thumbnail; backend limit является source of truth; normal runtime shutdown/restart сохраняет attachments, а database reset удаляет и DB rows, и files.
- Problems: Полный `tests.test_pipeline_memory` не является чистым baseline: один assertion failure и один `IndexError` в ASR summary normalization не связаны с chat attachment diff; ошибочно запрошенного модуля `tests.test_profiles` в репозитории нет.
- Technical debt: Нет.
- Next steps: Создать Stage 1 checkpoint и перейти к composer UI.
- Validation: `venv/bin/python -m compileall -q app backend tests` passed; `git diff --check` passed; `venv/bin/python -m unittest tests.test_chat_attachments -v` — 9 passed; `venv/bin/python -m unittest tests.test_model_router tests.test_chat_attachments -v` — 60 passed. broader `tests.test_pipeline_memory` — 61 passed, 1 unrelated failure, 2 errors (один error — отсутствующий запрошенный test module).
- Git checkpoint: `7b84d91` — Add chat attachment storage foundation

### Stage 2 — Composer Input and Preview
- Goal: Реализовать paste, multi-file drag-and-drop, picker, preview/remove/upload state и UI limit.
- Related files: `web_ui/gui_html.html`, `web_ui/js/app.js`, `web_ui/css/style.css`, frontend tests/manual matrix.
- [x] Completed: Implementation and validation.
- [x] Completed: Checkpoint commit.
- Architectural decisions: Clipboard image обрабатывается только при наличии image item; обычная text paste сохраняется; thumbnails используются вместо originals.
- Problems: Полноценного browser E2E suite нет; добавлен static UI contract test и выполнена ручная проверка живого localhost UI.
- Technical debt: Нет.
- Next steps: Создать Stage 2 checkpoint и перейти к capability/runtime boundary.
- Validation: `node --check web_ui/js/app.js` passed; `node tests/chat_attachments_ui.test.mjs` — 4 passed; `node tests/markdown_rendering.test.mjs` — 2 passed; `venv/bin/python -m unittest tests.test_chat_attachments -v` — 9 passed; compileall/diff-check passed. Manual localhost Browser: desktop 1280×720 dark and mobile 390×844 light; dedicated picker advertises `multiple`; upload/thumbnail/ready/delete passed; image-only paste passed; mixed text+image paste preserved text; mobile card stayed inside viewport with horizontal overflow and 44×44 remove target; focus reached native remove button. All test uploads/DB rows/temp files were removed; theme/viewport/clipboard restored.
- Git checkpoint: `18db044` — Add chat image composer workflow

### Stage 3 — Vision Capability and Runtime Boundary
- Goal: Реализовать capability resolver, direct Ollama multimodal payload, explicit fallback/error/resource policy и mocked tests.
- Related files: `app/config.py`, `app/services/models.py`, `backend/apps/chat/services/ollama_runtime.py`, `vision_runtime.py`, `vision_context.py`, `tests/test_chat_vision_runtime.py`, `tests/test_model_router.py`.
- [x] Completed: Implementation and validation.
- [x] Completed: Checkpoint commit.
- Architectural decisions: Images bypass LLM intent guessing; direct route разрешён только для подтверждённой vision capability; base64 существует только в transient Ollama request memory.
- Problems: Ollama runtime сейчас недоступен и vision-модели в project storage нет; live inference не запускался по policy.
- Technical debt: Нет.
- Next steps: Создать Stage 3 checkpoint и перейти к persisted chat task/SSE lifecycle.
- Validation: `venv/bin/python -m unittest tests.test_chat_vision_runtime tests.test_model_router -v` — 64 passed; `venv/bin/python -m unittest tests.test_chat_attachments -v` — 9 passed; compileall, JS syntax и diff-check passed. Проверены JSON/plain Ollama metadata, отдельный vision catalog, confirmed-only resolver, auto priority, text-only context route, byte limit, original-message immutability и native `/api/chat` images payload. Live inference/download intentionally not run.
- Git checkpoint: `2a608a6` — Add vision model capability runtime

### Stage 4 — Chat Task and Streaming Lifecycle
- Goal: Связать attachments с persisted user message/chat task, добавить preparing/analyzing/loading_model/generating, refresh/reconnect и cancel cleanup.
- Related files: `backend/apps/chat/routes.py`, `tasks.py`, vision services, DB repository, Web UI rendering, chat lifecycle tests.
- [x] Completed: Attachment preflight/ownership/limits, task-safe descriptors, persisted message/task binding, direct and text-model context routes, status/cancel/failure reconciliation and history thumbnails.
- [x] Completed: Focused lifecycle tests and compatible chat-task regressions.
- [x] Completed: Checkpoint commit.
- Architectural decisions: User message создаётся один раз; attachments валидируются до старта worker и передаются через task-safe serializable descriptors.
- Problems: Process-local registry не является durable queue; refresh восстанавливается через persisted message/task reconciliation и помечает незавершённый task/attachments failed после restart.
- Technical debt: Нет.
- Next steps: Создать Stage 4 checkpoint и перейти к OCR assist/degraded mode.
- Validation: `venv/bin/python -m unittest tests.test_chat_vision_lifecycle -v` — 4 passed; `tests.test_chat_vision_runtime` + `tests.test_chat_attachments` — 22 passed; targeted existing chat worker/stream/recovery tests passed; compileall, JS syntax и diff-check passed. Полный `tests.test_pipeline_memory` после совместимого worker signature вернулся к двум ранее зафиксированным ASR failures (1 failure + 1 error), без chat regression.
- Git checkpoint: `9cbe70e` — Connect vision attachments to chat tasks

### Stage 5 — OCR Assist and Accuracy
- Goal: Добавить OCR evidence как опциональный слой и explicit OCR-only degraded mode без изменения OCR Studio public contract.
- Related files: `backend/apps/chat/services/vision_context.py`, OCR adapter/service boundary, task/UI error/status flows, `tests/test_ocr_service.py`.
- [x] Completed: `auto`/`on`/`off` auxiliary OCR evidence, per-image labeling and explicit `ocr_only` degraded route.
- [x] Completed: OCR failure/error semantics and focused tests without changing OCR Studio routes.
- [x] Completed: Checkpoint commit.
- Architectural decisions: OCR output не подменяет vision молча; degraded mode маркируется явно.
- Problems: Live Tesseract/model workload не входит в обычный suite.
- Technical debt: Нет.
- Next steps: Создать Stage 5 checkpoint и перейти к profile-owned settings/cache API.
- Validation: `venv/bin/python -m unittest tests.test_chat_vision_context tests.test_chat_vision_lifecycle tests.test_chat_vision_runtime -v` — 21 passed; compileall и diff-check passed. Tesseract/live image OCR не запускались: adapter проверен mocked tests.
- Git checkpoint: `0928e45` — Add OCR assist to vision chat

### Stage 6 — Settings, Limits and Cache Cleanup
- Goal: Добавить backend profile-owned settings contract, effective limits, cache stats/cleanup и active-task protection.
- Related files: profile schemas/routes/config, attachment endpoints/repository/storage, unit/API tests.
- [x] Completed: Profile-owned validation/persistence for every vision setting and limit.
- [x] Completed: Cache statistics, profile/orphan cleanup reporting and active-task protection.
- [x] Completed: Checkpoint commit.
- Architectural decisions: `max_images_per_message` range 1–10, default 1; cleanup возвращает deleted/skipped count и bytes; отдельный UI всех vision-настроек реализуется в Stage 7.5.
- Problems: Нет.
- Technical debt: Нет.
- Next steps: Создать Stage 6 checkpoint и перейти к explicit text-only RAG export.
- Validation: `venv/bin/python -m unittest tests.test_vision_settings tests.test_chat_attachments tests.test_pipeline_memory.LocalGPTPipelineMemoryTestCase.test_profile_preferences_persist_streaming_enabled -v` — 13 passed; compileall и diff-check passed.
- Git checkpoint: `531e16e` — Add vision settings and cache controls

### Stage 7 — Explicit Text-only RAG Export
- Goal: Сохранять только редактируемый производный текст анализа как profile-scoped `vision_context`.
- Related files: `backend/apps/rag/routes.py`, `backend/apps/rag/service.py`, DB source repository, chat UI action/dialog, RAG tests.
- [x] Completed: Explicit editable Vision → RAG dialog/action and profile/session/message ownership checks.
- [x] Completed: Text-only `vision_context` indexing, safe reference metadata, binary data-URI rejection and independent deletion.
- [ ] Pending: Checkpoint commit.
- Architectural decisions: Auto-save запрещён; image binary/path не копируется в RAG content; metadata хранит attachment/message/session references.
- Problems: Нет.
- Technical debt: Нет.
- Next steps: Создать Stage 7 checkpoint и перейти к dedicated Vision settings/model tab.
- Validation: `venv/bin/python -m unittest tests.test_vision_rag` + two existing RAG/ASR context regressions — 5 passed; `node tests/chat_attachments_ui.test.mjs` — 5 passed; markdown tests — 2 passed; compileall, JS syntax и diff-check passed.
- Git checkpoint: pending

### Stage 7.5 — Dedicated Vision Models and Settings Tab
- Goal: Перед финальным live QA собрать отдельный Settings tab для vision model library и всех vision-owned controls, затем остановиться и передать пользователю точный download handoff.
- Related files: `web_ui/gui_html.html`, `web_ui/js/app.js`, `web_ui/css/style.css`, model catalog/routes, profile settings/cache endpoints, UI/static/manual tests.
- [ ] Pending: Implementation and validation.
- Architectural decisions: `qwen2.5vl:3b`, `qwen2.5vl:7b` и `gemma3:4b` не смешиваются с обычной chat library; tab показывает declared и runtime-confirmed capabilities отдельно; download/update/delete остаются явными действиями пользователя; в tab находятся `chat_images_enabled`, primary vision model/auto, fallback route, OCR assist, image count/byte/pixel/side limits, cache stats и cleanup.
- Problems: Vision-моделей сейчас нет в project storage, Ollama runtime недоступен.
- Technical debt: Нет.
- Next steps: Выполнить после Stage 7, создать checkpoint и сообщить пользователю, что можно скачать модели; Stage 8 не начинать до пользовательского handoff.
- Validation: pending
- Git checkpoint: pending

### Stage 8 — Regression, Documentation and Cleanup
- Goal: После загрузки vision-моделей пользователем выполнить controlled live smoke, закрыть static/unit/API/manual regression, обновить affected docs и удалить текущий progress-файл в terminal cleanup commit.
- Related files: affected docs, tests, runtime artifacts, `docs/progress/multimodal-chat-vision-progress.md`.
- [ ] Pending: User model download handoff, live QA, docs, `docs/CHANGELOG.md`, cleanup.
- Architectural decisions: Controlled live vision smoke выполняется только отдельно и осознанно; отсутствие запуска фиксируется как manual external validation, а не как passed.
- Problems: Нет.
- Technical debt: Нет.
- Next steps: Начинать только после Stage 7.5 checkpoint и подтверждения пользователя, что выбранные vision-модели скачаны.
- Validation: pending
- Git checkpoint: pending

## Overall Status
- Status: in progress
- Completed: Request/TЗ analysis, DOCX text/layout review, documentation-impact review, repository/code boundary inspection, Stage 1 implementation and validation.
- In progress: Stage 7 checkpoint.
- Pending: Stages 4–7.5, user model-download handoff, then Stage 8 final QA/docs/cleanup.
- Changed files since latest checkpoint: RAG schema/routes/service, Vision → RAG dialog/action, backend/UI tests and this progress file.
- Known problems: Existing ASR pipeline-memory assertions are not a clean baseline; Ollama runtime сейчас недоступен; в project storage нет vision model; live vision smoke не разрешён в обычной validation.
- Technical debt: Нет.
- Next action: Inspect/stage/commit Stage 7, then implement Stage 7.5 dedicated Vision tab and stop for user download.
- Latest Git checkpoint: `2a608a6` — Add vision model capability runtime.

## Continuation Prompt
Continue work on `multimodal-chat-vision` using `docs/progress/multimodal-chat-vision-progress.md`. Current status: Stage 4 implemented/validated, checkpoint pending. Completed checkpoints: Stage 1 `7b84d91`; Stage 2 `18db044`; Stage 3 `2a608a6`. Stage 4 adds attachment ownership/limit preflight, direct/context vision worker routes, persisted task/message linkage, vision statuses, cancellation/restart reconciliation and history thumbnails; focused lifecycle tests pass. Remaining: commit Stage 4, Stages 5–7.5, then stop for user model download before Stage 8. Problems/blockers: broader pipeline-memory suite retains two pre-existing ASR summary failures; Ollama runtime unavailable and no vision model exists; live inference/download must not run automatically. Preserve: confirmed-only capabilities, transient base64, explicit OCR/degraded behavior, no binary RAG ingest, dedicated Vision tab and user gate after Stage 7.5.
