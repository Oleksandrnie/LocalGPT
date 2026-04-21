# Backend Structure

Текущий backend разделён по mini-app зонам, чтобы код можно было искать не по grep, а по папкам.

## Mini-app folders

- `backend/apps/chat/`
  - `routes.py` — chat API
  - `service.py` — LLM/chat logic
  - `tasks.py` — background generation tasks

- `backend/apps/asr/`
  - `routes.py` — transcribe API
  - `transcripts.py` — transcript history CRUD
  - `models_routes.py` — Whisper model management
  - `whisper.py` — ASR pipeline
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
- `app/routes/storage.py`
- `app/routes/criteria.py`

Это transitional layout:
- runtime уже может стартовать через `backend.server:app`;
- старые `app/...` импорты оставлены как compatibility shim;
- следующая cleanup-итерация может вынести shared/core слой из `app/` в отдельный `backend/core/`.
