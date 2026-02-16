# LocalGPT Whisper Transcriber

LocalGPT теперь работает как локальный транскрибатор аудио/видео с историей текстов и записью голоса.

## Что умеет
- Локальная транскрибация через `faster-whisper`.
- Выбор модели: `tiny`, `base`, `small`, `medium`, `large-v3`, `large-v3-turbo`.
- Запись голоса в браузере (приоритет `M4A/AAC`, fallback `WebM/Opus`).
- История транскрибаций в файловом хранилище (`app/data/transcripts/*.json`).
- Единый тёмный интерфейс, адаптированный под desktop и phone.

## Запуск
1. Требования: Python 3.10+, ffmpeg.
2. Запуск из корня проекта:
   ```bash
   python3 run_localgpt.py
   ```
3. Ручной запуск:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r app/requirements.txt
   uvicorn app.server:app --host 127.0.0.1 --port 8000 --reload
   ```
4. UI: `http://127.0.0.1:8000/ui/gui_html.html`

## API
- `GET /health`
- `GET /whisper/models`
- `POST /whisper/models/prepare`
- `GET /whisper/models/prepare/{task_id}`
- `POST /transcribe` (multipart: `file`, `model`, `source_type`)
- `GET /transcripts`
- `GET /transcripts/{id}`
- `POST /transcripts`
- `PATCH /transcripts/{id}`

## Хранилище
- Транскрибации: `app/data/transcripts/<id>.json`
- Формат записи включает:
  - `id`, `created_at`, `updated_at`
  - `source_type`, `source_name`
  - `model`, `language`, `duration_sec`
  - `preview`, `text`

## Конфигурация (`.env`)
Основные параметры смотрите в `.env.example`:
- `MODELS_DIR`
- `WHISPER_MODELS_DIR`
- `HF_CACHE_DIR`
- `CTRANSLATE2_CACHE_DIR`
- `TRANSCRIPTS_DIR`
- `WHISPER_MODEL_SIZE`
- `WHISPER_COMPUTE_TYPE`
- `WHISPER_DEVICE`
- `WHISPER_BEAM_SIZE`
- `WHISPER_FALLBACK_LANGUAGE`
- `HF_ENDPOINT` (по умолчанию `https://huggingface.co`)
- `HF_FALLBACK_ENDPOINT` (опциональный резервный endpoint)
- `HF_TRUST_ENV` (`1` если нужно использовать `HTTP_PROXY`/`HTTPS_PROXY`)

## Smoke checklist
1. Выбрать аудио/видео файл -> транскрибация стартует автоматически.
2. Нажать `⏺`, записать >=3 сек -> запись сохраняется и автоматически транскрибируется.
3. Кнопки `copy | save | clear` работают с центральным полем.
4. История показывает дату/время и preview.
5. Клик по записи открывает модалку; `send` переносит текст в центральное поле.
