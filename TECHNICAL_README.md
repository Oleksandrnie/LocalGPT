# LocalGPT Technical README

Технический документ для обсуждения с инженерами и ИИ-ассистентами.
Фокус: unified runtime, prompt assembly, ASR pipeline, summary memory, RAG и ограничения локального Ollama.

## 1. Runtime-схема

- Backend: `FastAPI` (`backend.server:app`) с mini-app layout.
- LLM gateway: OpenAI-compatible клиент к локальному Ollama (`LOCAL_BASE_URL`, обычно `http://localhost:11434/v1`).
- ASR: `whisper.cpp` by default for Metal/CoreML setups; `faster-whisper` remains an explicit CPU fallback.
- TTS: `Piper`.
- OCR: `Tesseract`, v1 только изображения.
- Storage: `SQLite` (`app/db/localgpt.db`) + файловое хранилище runtime-артефактов.
- UI: static Web UI (`web_ui/`).
- Models/cache root: только `/models`.

`compare-branch/` не участвует в runtime и остаётся только reference-only.

### LLM lifecycle

- Bootstrap создаёт `venv`, ставит `app/requirements.txt`, готовит директории и проверяет Ollama, но не выбирает chat-модель автоматически.
- `LOCAL_MODEL` может быть пустым; пустое значение означает `Модель не загружена`.
- Startup не запускает `ollama pull`, не скачивает `qwen2.5:3b` и не пишет fallback в `.env`.
- `/models` только читает локальный список и текущие download task statuses.
- `/models/pull` запускается только после явного действия пользователя и подтверждения в UI.
- Если локальных chat-моделей нет, UI оставляет input активным, но отключает отправку и показывает toast; backend-запрос к LLM не создаётся.

## 2. Mini-app layout

- `backend/apps/chat/` — chat API, prompt assembly, background generation, debug endpoints.
- `backend/apps/asr/` — transcription, Whisper model management, transcript storage, ASR pipeline.
- `backend/apps/tts/` — Piper generation, voice library, history, audio postprocess.
- `backend/apps/ocr/` — image OCR.
- `backend/apps/rag/` — local source ingestion, chunks, local hash embeddings, retrieval context.

Shared/core слой пока остаётся в `app/`: `config`, `db`, `schemas`, `routes/profiles`, `routes/models`, `routes/meta`, `services/models`.

### ASR backend selection

`WHISPER_BACKEND` controls runtime transcription:

- `whisper_cpp` — default ASR path; require `whisper.cpp` and fail clearly if its binary/model is missing;
- `auto` — use `whisper.cpp` only when `whisper-cli` and a matching GGML model file are present, otherwise fall back to `faster-whisper`;
- `faster_whisper` — Python fallback: `faster-whisper` -> CTranslate2 -> configured `WHISPER_DEVICE` / `WHISPER_COMPUTE_TYPE`.

`whisper.cpp` model files are separate from faster-whisper snapshots and live under `models/whisper_cpp` by default. `WHISPER_CPP_MODEL_PATH` can be a fixed path or a template with `{model}`, for example `models/whisper_cpp/ggml-{model}.bin`.

`tools/setup_whisper_cpp_macos.sh <model>` bootstraps the local `whisper.cpp` tree under `models/whisper_cpp/source`, builds a Metal/CoreML CLI, links it to `models/whisper_cpp/bin/whisper-cli`, and downloads `ggml-<model>.bin` plus the CoreML encoder zip when available. When `WHISPER_BACKEND` is `auto` or `whisper_cpp`, `/whisper/models/prepare` downloads GGML/CoreML files from `ggerganov/whisper.cpp` instead of faster-whisper snapshots.

## 3. Chat request flow

1. UI отправляет `POST /chat/tasks`.
2. Backend валидирует profile/session/model.
3. Если модель не выбрана, возвращается readable `chat_model_not_selected` до создания session.
4. Если выбранная chat-модель не установлена, возвращается readable `chat_model_missing`; auto-pull не запускается.
5. Считается `effective_settings = defaults + profile/model overrides`.
6. Подгружается summary memory.
7. Подгружается только short raw history по `mem_turns`.
8. Если включён RAG, выполняется retrieval по активному профилю.
9. Собирается `messages[]`.
10. Запрос отправляется в Ollama OpenAI-compatible endpoint.
11. Ответ очищается через `sanitize_reply()`, сохраняется в SQLite и возвращается UI.

## 4. Prompt assembly order

Текущий порядок:

1. system prompt по роли (`system_prompt_for(role)`);
2. profile-level system prompt, если задан;
3. profile/user context из request;
4. summary memory;
5. relevant RAG context;
6. processed transcript / structured context;
7. criteria;
8. short raw history (`mem_turns`);
9. current user query.

Сырой длинный transcript не должен быть основным способом передачи контекста. Для ASR Studio используется processed pipeline output.

В финальный system guardrail также добавляются правила оформления расчётов и цен:

- не использовать LaTeX, MathML, markdown-формулы и синтаксис `\[...\]`, `\( ... \)`, `\text{...}`;
- не использовать запятую как разделитель тысяч (`35,690 ₽` -> `35 690 ₽`);
- суммы писать обычным человекочитаемым текстом.

`sanitize_reply()` дополнительно чистит типичный LaTeX-output локальных моделей и нормализует валютные тысячи.

## 5. Memory

`mem_turns` — это только short-term window:

- default: `6`;
- нормальный диапазон: `4-8`;
- выше `12` UI показывает предупреждение;
- старые raw-сообщения физически не удаляются, но не обязаны попадать в prompt.

Summary memory:

- хранится в таблице `session_summaries`;
- источники: `chat`, `asr`, `ocr`, `manual`;
- используется перед short raw history;
- нужна для длинных диалогов вместо раздувания `mem_turns`.

## 6. ASR pipeline

Pipeline:

```text
raw ASR transcript
-> cleaner
-> segmenter
-> speaker resolver
-> structurer
-> summary
-> DB
-> optional chat context / memory
```

API:

- `POST /transcripts/{id}/pipeline`
- `GET /transcripts/{id}/pipeline/latest`
- `PATCH /transcripts/{id}/pipeline/{run_id}/speakers`
- `POST /transcripts/{id}/pipeline/{run_id}/summary`

Хранится:

- raw transcript;
- cleaned transcript;
- segments;
- speaker mapping;
- manual speaker overrides;
- structured JSON;
- summary;
- stage timings;
- warnings;
- used settings;
- optional debug artifacts.

Основная история pipeline хранится в `transcript_pipeline_runs`. Для удобства `ASR Studio` последние `summary`, `structured_json` и `latest_pipeline_run_id` также денормализуются в запись `transcripts`, а `name` обновляется по теме/summary. Это не заменяет run history, а даёт понятные названия и быстрый доступ в базе транскрибаций.

Speaker rules:

- реальные имена не угадываются;
- без подтверждения используются `Speaker_1`, `Speaker_2` или `Unknown speaker`;
- есть `confidence` / `uncertain`;
- ручные overrides в UI используются при повторной генерации summary.

Structurer теперь разделяет:

- `decisions` — только подтверждённые решения;
- `proposals` — предложения и варианты;
- `agreements` — зафиксированные договорённости;
- `tasks`;
- `risks`;
- `open_questions`;
- `next_steps`.

## 7. RAG

RAG в текущей итерации — локальный MVP без внешних API и без полноценного vector DB.

Схема:

```text
profile RAG files
-> structured JSON companions
-> source_documents
-> document_chunks
-> document_embeddings
-> retrieval
-> prompt context
```

Папки:

- root: `rag_sources/`;
- profile folder: `rag_sources/profile_<id>_<name>/`;
- новый профиль получает пустую папку;
- при удалении профиля папка удаляется;
- active profile видит только свои RAG-файлы.

Поддерживаемые файлы:

- `.md`;
- `.json`;
- `.txt`.

Правила MD/JSON:

- Markdown — пояснение;
- JSON — source of truth;
- если JSON конфликтует с Markdown, prompt говорит использовать JSON;
- если `.md` добавлен без `.json`, система создаёт авто-JSON;
- ручной `.json` не перезаписывается;
- UI-кнопка `Индексировать` запускает force ingest: пересобирает chunks/embeddings и авто-JSON с `generated_by: localgpt_auto_structurer`, не трогая ручные JSON;
- файлы удаляются через `DELETE /rag/files?profile_id=...&path=...`; при удалении `.md` также удаляется его авто-JSON companion, если он был создан LocalGPT.

Если `rag_enabled=true`, chat runtime выполняет retrieval для каждого сообщения активного профиля. Поиск использует текущий user query плюс несколько последних user-сообщений из short history, чтобы короткие follow-up фразы вроде “для этого есть rag” всё равно могли найти релевантный контекст. В `used_settings` возвращаются `rag_enabled_effective`, `rag_chunks_used` и `rag_context_chars`.

Больше деталей: `rag_sources/README.md`.

Таблицы под RAG уже есть:

- `source_documents`;
- `document_chunks`;
- `document_embeddings`.

`source_type` для текущего MVP: `manual_file`.
Планируемые типы: `manual_file`, `asr_transcript`, `ocr_text`, `chat_summary`, `profile_memory`.

## 7.1. Database maintenance

UI-кнопки обслуживания БД находятся в settings-секции `Whisper модели`.

- `POST /database/cleanup` удаляет осиротевшие данные после удаления чатов: transcripts без session, chat summaries без session и non-`manual_file` source documents без session; после удаления запускает `VACUUM`, если `vacuum=true`.
- Мягкая очистка сохраняет `ASR Studio` transcripts (`labels.origin=asr_tool`) и ручные RAG-документы (`source_type=manual_file`).
- `POST /database/reset` требует `confirm=RESET_DATABASE`, отменяет активные runtime tasks, удаляет профильные RAG-папки, очищает profile-owned SQLite tables через cascade и пересоздаёт профиль `Default`.
- Очистка БД не удаляет локальные LLM/ASR/TTS model artifacts из `/models`.

## 8. Settings

Настройки объединяются из:

1. `.env` / `app/config.py`;
2. profile preferences;
3. model overrides в SQLite (`profile + model`).

Основные поля:

- `temperature`;
- `max_tokens`;
- `num_ctx`;
- `mem_turns`;
- `pipeline_enabled`;
- `summary_memory_enabled`;
- `rag_enabled`;
- `default_pipeline_preset`;
- `max_transcript_chars`;
- `max_context_chars`;
- `summary_memory_limit`;
- `rag_top_k`;
- `rag_max_context_chars`;
- per-stage pipeline settings.

Profile metadata редактируется отдельно от model settings:

- `POST /profiles` принимает `name`, `description`, `color`, `system_prompt`;
- `name` trim-ится и обязателен при создании;
- `description` и `system_prompt` необязательны;
- `PATCH /profiles/{profile_id}` обновляет metadata профиля и profile-level system prompt одним запросом;
- UI settings имеет два режима: редактирование существующего профиля и создание нового профиля.

Рекомендуемые температуры:

- chat/factual/RAG: `0.2-0.4`;
- обычный свободный чат: `0.7-0.8`;
- cleaner: `0.2`;
- segmenter: `0.1`;
- speaker resolver: `0.1`;
- structurer: `0.3`;
- summary: `0.3`;
- code assistant: `0.2-0.4`.

## 9. num_ctx

`num_ctx` хранится в settings и возвращается в `used_settings` как:

- `num_ctx_requested`;
- `num_ctx_applied = false`;
- `num_ctx_apply_method = openai_compatible_not_supported`.

Причина: через Ollama OpenAI-compatible endpoint context size нельзя стабильно применить per request. Для фактического изменения контекста нужен Ollama/Modelfile-level подход.

## 10. Debug / observability

Dev/admin endpoints:

- `GET/POST /chat/debug/prompt`;
- `GET /chat/debug/pipeline?run_id=...`.

Логи:

- `tmp_logs/chat.log`;
- `tmp_logs/pipeline.log`.

Pipeline log содержит stage, elapsed time, input/output sizes, errors, truncation flag и used settings.

## 11. LAN

Основной launcher:

- `start_localgpt_lan.sh`;
- `start_localgpt_lan.command`.

Legacy alias:

- `LTrnsrb.command`.

LAN launcher стартует backend с предпочтением `127.0.0.1:8000`, но если порт занят, выбирает следующий свободный локальный порт; Caddy остаётся на `https://<lan-ip>:8443` и проксирует на фактический backend-порт.
Определение LAN IP предпочитает Wi-Fi/private IPv4 (`192.168.*`, `10.*`, `172.16-31.*`), чтобы не отдавать VPN/Tailscale IP телефону в обычной Wi-Fi сети.

## 12. Static UI system

Основной UI — `web_ui/gui_html.html` + `web_ui/js/app.js` + `web_ui/css/style.css`.

Текущий UI v2:

- floating topbar с blur, мягкой тенью и без жёсткого нижнего разделителя;
- sidebar с glass/blur-слоем и collapsible state;
- `localStorage.sidebar_open` хранит состояние sidebar;
- `Cmd+B` / `Ctrl+B` переключает sidebar;
- toast-система отображает уведомления строго под topbar по центру;
- нижняя composer-зона не содержит системных статусов;
- `RAG` topbar button показывает состояние активного профиля через dot и glow;
- soft message cards используют прозрачность, blur, внутренний свет и shadow-контур вместо жёсткого border;
- единый `AppSelect` строится JS-слоем поверх скрытого native `<select>`.

Theme system:

- dark theme — базовая;
- light theme включается классом `body.theme-light`;
- dark theme использует `body.theme-dark`;
- topbar `ThemeToggle` переключает тему;
- состояние хранится в `localStorage` через `localgpt_simple_theme`;
- light theme использует semantic tokens (`--bg`, `--bg-soft`, `--text`, `--text-muted`, `--border`, `--accent-*`) и overrides для topbar/sidebar/messages/composer/modals/tools;
- light theme визуально строится на `#F6F7FB`, radial-пятнах, glass-слоях, blur и мягких тенях.

UI component rules:

- подробности в `docs/ui-components.md`;
- видимые native select запрещены;
- новые кнопки/dropdowns/toasts должны использовать существующие UI-классы и состояния.

## 13. Git/runtime hygiene

В git не должны попадать:

- `.env`;
- SQLite DB;
- chat/asr/tts task JSON;
- logs;
- model files and caches;
- profile RAG contents.

В git оставляется только структура (`.gitkeep`) и документация (`rag_sources/README.md`).

## 14. Test coverage

Текущие ключевые проверки:

- empty Ollama model list не запускает auto-pull;
- chat task без выбранной модели возвращает `chat_model_not_selected` и не создаёт session;
- readable `chat_model_missing`;
- ASR Studio default model `large-v3-turbo`;
- profile create/update with optional system prompt;
- summary memory before short history;
- profile system prompt in prompt;
- RAG profile isolation;
- JSON RAG source-of-truth context;
- ASR summary uses cleaned text, not raw transcript;
- speaker overrides affect regenerated summary;
- global response formatting guardrail is included in chat prompt;
- `sanitize_reply()` removes common LaTeX currency formatting and normalizes thousands;
- DB additive migrations.

Запуск:

```bash
./venv/bin/python -m unittest discover tests
```
