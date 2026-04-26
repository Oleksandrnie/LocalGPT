# LocalGPT Technical README

Технический документ для обсуждения с инженерами и ИИ-ассистентами.
Фокус: unified runtime, prompt assembly, ASR pipeline, summary memory, RAG и ограничения локального Ollama.

## 1. Runtime-схема

- Backend: `FastAPI` (`backend.server:app`) с mini-app layout.
- LLM gateway: OpenAI-compatible клиент к локальному Ollama (`LOCAL_BASE_URL`, обычно `http://localhost:11434/v1`).
- ASR: `faster-whisper`.
- TTS: `Piper`.
- OCR: `Tesseract`, v1 только изображения.
- Storage: `SQLite` (`app/db/localgpt.db`) + файловое хранилище runtime-артефактов.
- UI: static Web UI (`web_ui/`).
- Models/cache root: только `/models`.

`compare-branch/` не участвует в runtime и остаётся только reference-only.

## 2. Mini-app layout

- `backend/apps/chat/` — chat API, prompt assembly, background generation, debug endpoints.
- `backend/apps/asr/` — transcription, Whisper model management, transcript storage, ASR pipeline.
- `backend/apps/tts/` — Piper generation, voice library, history, audio postprocess.
- `backend/apps/ocr/` — image OCR.
- `backend/apps/rag/` — local source ingestion, chunks, local hash embeddings, retrieval context.

Shared/core слой пока остаётся в `app/`: `config`, `db`, `schemas`, `routes/profiles`, `routes/models`, `routes/meta`, `services/models`.

## 3. Chat request flow

1. UI отправляет `POST /chat/tasks`.
2. Backend валидирует profile/session/model.
3. Если chat-модель не установлена, возвращается readable `chat_model_missing`; auto-pull не запускается.
4. Считается `effective_settings = defaults + profile/model overrides`.
5. Подгружается summary memory.
6. Подгружается только short raw history по `mem_turns`.
7. Если включён RAG, выполняется retrieval по активному профилю.
8. Собирается `messages[]`.
9. Запрос отправляется в Ollama OpenAI-compatible endpoint.
10. Ответ очищается, сохраняется в SQLite и возвращается UI.

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
- если `.json` уже существует, авто-генератор его не перезаписывает.

Больше деталей: `rag_sources/README.md`.

Таблицы под RAG уже есть:

- `source_documents`;
- `document_chunks`;
- `document_embeddings`.

`source_type` для текущего MVP: `manual_file`.
Планируемые типы: `manual_file`, `asr_transcript`, `ocr_text`, `chat_summary`, `profile_memory`.

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

LAN launcher стартует backend на `127.0.0.1:8000` и Caddy на `https://<lan-ip>:8443`.
Определение LAN IP предпочитает Wi-Fi/private IPv4 (`192.168.*`, `10.*`, `172.16-31.*`), чтобы не отдавать VPN/Tailscale IP телефону в обычной Wi-Fi сети.

## 12. Git/runtime hygiene

В git не должны попадать:

- `.env`;
- SQLite DB;
- chat/asr/tts task JSON;
- logs;
- model files and caches;
- profile RAG contents.

В git оставляется только структура (`.gitkeep`) и документация (`rag_sources/README.md`).

## 13. Test coverage

Текущие ключевые проверки:

- empty Ollama model list не запускает auto-pull;
- readable `chat_model_missing`;
- ASR Studio default model `large-v3-turbo`;
- summary memory before short history;
- profile system prompt in prompt;
- RAG profile isolation;
- JSON RAG source-of-truth context;
- ASR summary uses cleaned text, not raw transcript;
- speaker overrides affect regenerated summary;
- DB additive migrations.

Запуск:

```bash
./venv/bin/python -m unittest discover tests
```
