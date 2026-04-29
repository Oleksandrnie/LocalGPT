# Backend Structure

Текущий backend разделён по mini-app зонам, чтобы код можно было искать не по grep, а по папкам.

## Mini-app folders

- `backend/apps/chat/`
  - `routes.py` — chat API
  - `service.py` — LLM/chat logic, prompt assembly, response sanitizing and calculation/currency formatting guardrails
  - `tasks.py` — background generation tasks
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

## UI contracts

- Static UI живёт в `web_ui/`; backend отдаёт его как runtime asset.
- `ThemeToggle` в topbar переключает `body.theme-dark` / `body.theme-light` и сохраняет состояние в `localStorage`.
- Sidebar state хранится в `localStorage.sidebar_open` и переключается через UI trigger или `Cmd+B` / `Ctrl+B`.
- RAG state button в topbar должен отражать `rag_enabled` активного профиля, а не быть декоративным индикатором.
- Все системные уведомления должны идти через toast под topbar, не через нижнюю input area.
- Если нет локальной chat-модели, composer input остаётся активным, но send disabled; попытка отправки показывает toast и не создаёт backend LLM request.
- Запуск загрузки LLM-модели требует явного подтверждения пользователя.
- Видимые select-контролы должны использовать кастомный `AppSelect`; native `<select>` допустим только как скрытый backing-state.
