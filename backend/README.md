# Backend Structure

Текущий backend разделён по mini-app зонам, чтобы код можно было искать не по grep, а по папкам.

## Mini-app folders

- `backend/apps/chat/`
  - `routes.py` — chat API
  - `service.py` — LLM/chat logic, prompt assembly, response sanitizing and calculation/currency formatting guardrails
  - `tasks.py` — background generation tasks; current contract supports polling plus SSE (`POST /chat/tasks`, `GET /chat/tasks/{id}`, `GET /chat/tasks/{id}/events`), assistant reply and partial chunks are persisted into the pre-created assistant message
  - debug endpoints for assembled prompt inspection

- `backend/apps/asr/`
  - `routes.py` — transcribe API
  - `transcripts.py` — transcript history CRUD, including latest summary/structured result fields
  - `pipeline_routes.py` — ASR pipeline API
  - `pipeline.py` — cleaner/segmenter/speaker resolver/structurer/summary flow and transcript result sync
  - `models_routes.py` — Whisper model management
  - `whisper.py` — faster-whisper integration
  - `tasks.py` — background transcription tasks
  - `downloads.py` — local Whisper model downloads/update checks

- `backend/apps/ocr/`
  - `routes.py` — OCR API
  - `service.py` — OCR pipeline and screenshot auto-crop

- `backend/apps/tts/`
  - `router.py` — TTS API
  - `service.py` — TTS history/generation/download logic
  - `audio_postprocess.py` — speed post-processing
  - `providers/` — concrete TTS providers
  - `schemas.py` — TTS request schemas

- `backend/apps/rag/`
  - `routes.py` — RAG status/ingest/upload/search API
  - `service.py` — profile folders, MD->JSON companions, chunking, local embeddings, retrieval context

- `backend/apps/plugins/`
  - `registry.py` — Plugin Registry v0: manifest scan, trusted/untrusted state, enabled state, network address aggregation
  - `routes.py` — plugin API (`GET /plugins`, `POST /plugins/{plugin_id}/enabled`, `GET /plugins/network-addresses`)
  - `tailscale.py` — trusted backend-owned handler for official/internal Tailscale remote access plugin

## Shared/core layer

Пока shared-слой ещё остаётся в `app/`:

- `app/config.py`
- `app/db.py`
- `app/storage.py`
- `app/roles.py`
- `app/schemas/`
- `app/services/models.py`
- `app/services/criteria.py`
- `app/services/timeline.py`
- `app/routes/meta.py`
- `app/routes/models.py`
- `app/routes/profiles.py`
  - `GET /profiles`
  - `POST /profiles` creates a profile with required `name` and optional `description`, `color`, `system_prompt`
  - `PATCH /profiles/{profile_id}` updates profile metadata and profile-level `system_prompt`
  - `PATCH /profiles/{profile_id}/preferences` updates runtime preferences such as ASR/TTS/chat settings
- `app/routes/storage.py`
- `app/routes/criteria.py`
- `app/routes/meta.py`
  - `POST /database/cleanup` removes orphaned chat-derived SQLite rows and can run `VACUUM`
  - `POST /database/reset` fully clears profile-owned DB data, deletes profile RAG folders and recreates `Default`

Это transitional layout:
- runtime уже может стартовать через `backend.server:app`;
- старые `app/...` импорты оставлены как compatibility shim;
- следующая cleanup-итерация может вынести shared/core слой из `app/` в отдельный `backend/core/`.

## Current runtime contracts

- Runtime не зависит от `compare-branch/`.
- Все модели и кэши должны лежать внутри `/models`.
- Bootstrap backend/launcher не выбирает fallback LLM и не запускает `ollama pull`; приложение должно стартовать без chat-модели.
- `LOCAL_MODEL` может быть пустым. Chat API в этом случае возвращает `chat_model_not_selected` до создания session.
- Если модель выбрана, но не установлена локально, Chat API возвращает `chat_model_missing`; загрузка возможна только через явный `/models/pull`.
- SQLite и runtime-артефакты не коммитятся.
- DB maintenance не удаляет локальные model artifacts: cleanup/reset работают только с SQLite и профильными RAG-папками.
- RAG-файлы профилей не коммитятся; в git остаётся только `rag_sources/README.md` и `.gitkeep`.
- OCR v1 ограничен изображениями, PDF OCR не входит в текущую итерацию.
- Chat prompt всегда получает общий guardrail: не использовать LaTeX/MathML/markdown-формулы для расчётов и не писать запятые как разделитель тысяч в ценах.
- `sanitize_reply()` нормализует типичный LaTeX currency output локальных моделей перед сохранением ответа.
- Plugin Registry v0 читает `plugins/*/plugin.json` только как metadata. Код из `plugins/` не импортируется и не исполняется.
- Unknown plugin ids отображаются как untrusted и не могут стать effectively enabled. Plugins disabled by default.
- Trusted plugin behavior живёт только в backend-owned handlers, например `backend/apps/plugins/tailscale.py`.
- Tailscale handler делает read-only status checks и отдаёт manual command text, но не запускает `tailscale serve`, не включает Funnel и не открывает public ports.

## Plugin API contracts

Current plugin API:

- `GET /plugins` — список valid/invalid manifests, trusted/untrusted state, enabled/effective_enabled, docs status, permissions, dangerous permissions, trusted handler status;
- `POST /plugins/{plugin_id}/enabled` — сохраняет локальное enabled state; untrusted plugin cannot be enabled effectively;
- `GET /plugins/network-addresses` — отдаёт copyable backend-provided network address items.

Network address providers:

- core LAN item строится из существующего `/health.lan_url` helper и появляется только когда LAN HTTPS listener реально доступен;
- trusted plugin items добавляются только если plugin trusted/enabled и handler подтверждает доступный адрес;
- frontend не должен hardcode-ить Tailscale URLs, а должен копировать только backend-provided items.

## UI contracts

- Static UI живёт в `web_ui/`; backend отдаёт его как runtime asset.
- `ThemeToggle` в topbar переключает `body.theme-dark` / `body.theme-light` и сохраняет состояние в `localStorage`.
- Sidebar state хранится в `localStorage.sidebar_open` и переключается через UI trigger или `Cmd+B` / `Ctrl+B`.
- Icon-only RAG state button в topbar должен отражать `rag_enabled` активного профиля: dot показывается только в active/on состоянии.
- Все системные уведомления должны идти через toast под topbar, не через нижнюю input area.
- Если нет локальной chat-модели, composer input остаётся активным, но send disabled; попытка отправки показывает toast и не создаёт backend LLM request.
- Запуск загрузки LLM-модели требует явного подтверждения пользователя; normal progress отображается в download-card без повторяющихся toast.
- Видимые select-контролы должны использовать кастомный `AppSelect`; native `<select>` допустим только как скрытый backing-state.
- Checkbox `Стриминг ответов` находится первой карточкой в Settings → `Чат / LLM`, сохраняется сразу при переключении в profile preferences как `streaming_enabled` и отправляется в `POST /chat/tasks` как `stream`. Новые профили получают `streaming_enabled=true` по умолчанию.
- Settings -> Plugins показывает trusted/untrusted plugins, permissions, dangerous permissions, docs status, security warnings, handler status и enable/disable control.
- Topbar network address button сохраняет fast path: 0 адресов disabled/warning, 1 адрес copied by left click, 2+ адреса left-click menu. Right-click-only selection запрещён.
- Assistant cards должны рендериться по persistent `message.status`; локальный optimistic placeholder не является источником generation state.

## Current chat task contract

Актуальный chat runtime перед SSE rollout:

- `POST /chat/tasks` создаёт или продолжает session, валидирует модель и запускает background process;
- autorouter, если выбран `Auto / Smart Router`, завершает route selection до старта answer-модели и отдаёт route metadata через `used_settings` / `model_selected`; user-facing `router_notice` для normal-success routing пустой, чтобы UI не показывал success-toast про confidence/выбранную модель;
- static UI передаёт `stream` из profile preference `settings.streaming_enabled`;
- task state доступен через polling `GET /chat/tasks/{task_id}` и lifecycle SSE `GET /chat/tasks/{task_id}/events`;
- если request содержит `stream=true`, backend вызывает native Ollama streaming API для финальной answer-модели и отдаёт `delta` через SSE;
- если request не содержит `stream` или содержит `stream=false`, backend использует non-streaming fallback: ждёт полный ответ, не отдаёт `delta`, но сохраняет lifecycle в том же assistant-message;
- SSE events: `status`, `model_selected`, `delta`, `done`, `error`, `cancelled`;
- storage уже поддерживает persistent assistant lifecycle fields и partial content;
- user-message и assistant-message сохраняются при старте task; assistant-message получает `status=generating` и затем обновляется task-финализацией;
- response payload содержит `id`, `task_id`, `session_id`, `conversation_id`, `user_message_id`, `assistant_message_id`, `state`, `model_name`, `used_settings`, `stream`, `streaming_enabled`;
- отмена идёт через `POST /chat/tasks/{task_id}/cancel`;
- static UI использует SSE для `stream=true` и fallback polling для non-streaming или оборванного SSE-соединения;
- при повторном открытии чата UI восстанавливает active task из persisted assistant-message `task_id`;
- если runtime task уже не найден, `GET /chat/tasks/{task_id}`, SSE endpoint и cancel route помечают связанное active assistant-message как `failed`, чтобы состояние не зависало в `generating`.

Task 10 verification для backend contract:

- unit tests покрывают streaming/non-streaming worker paths, SSE `delta`, missing-model failures, stale-task reconciliation и autorouter selection без token streaming;
- API-smoke на временной SQLite-базе проверяет `POST /chat/tasks`, `GET /chat/tasks/{id}/events`, `GET /sessions/{id}/messages` и failed recovery paths;
- backend smoke запускает `backend.server:app` через uvicorn и проверяет `/health` плюс static UI route;
- live Ollama smoke проверяет реальный answer-model streaming с SSE `delta`, `done` и persisted assistant-message;
- Ollama Metal-to-CPU fallback перед CPU retry повторно выгружает модель, чтобы не переиспользовать зависший Metal runner.

## Chat message lifecycle storage

`app/db.py` хранит для `chat_messages` поля `status`, `model`, `updated_at`, `error`, `generation_started_at`, `generation_finished_at`, `is_partial` и `task_id`.

Lifecycle statuses:

- `generating` — assistant-message создан, ответ ещё не готов;
- `streaming` — content приходит частями;
- `completed` — ответ завершён успешно;
- `failed` — генерация завершилась ошибкой, текст ошибки хранится в `error`;
- `cancelled` — генерация отменена.

Legacy rows мигрируют в `completed`, поэтому старая история читается как обычные завершённые сообщения.
