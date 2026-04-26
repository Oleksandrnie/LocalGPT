# Backend Structure

Текущий backend разделён по mini-app зонам, чтобы код можно было искать не по grep, а по папкам.

## Mini-app folders

- `backend/apps/chat/`
  - `routes.py` — chat API
  - `service.py` — LLM/chat logic
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

Это transitional layout:
- runtime уже может стартовать через `backend.server:app`;
- старые `app/...` импорты оставлены как compatibility shim;
- следующая cleanup-итерация может вынести shared/core слой из `app/` в отдельный `backend/core/`.

## Current runtime contracts

- Runtime не зависит от `compare-branch/`.
- Все модели и кэши должны лежать внутри `/models`.
- SQLite и runtime-артефакты не коммитятся.
- RAG-файлы профилей не коммитятся; в git остаётся только `rag_sources/README.md` и `.gitkeep`.
- OCR v1 ограничен изображениями, PDF OCR не входит в текущую итерацию.
