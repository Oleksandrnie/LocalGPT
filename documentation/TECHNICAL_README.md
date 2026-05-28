> Source: `TECHNICAL_README.md`
> This is a documentation-hub copy. Update the source document first, then refresh this copy.
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
- Source of truth для LLM install state — тот Ollama runtime, который задан в `.env` (`OLLAMA_HOST`/`LOCAL_BASE_URL`) и его `OLLAMA_MODELS_DIR`, обычно project-scoped `models/ollama`. Plain shell `ollama list` без этих env может смотреть на другой daemon/store и не отражать состояние приложения.
- `/models` возвращает раздельные признаки `configured`, `installed`/`runtime_installed`, `active`, `downloading`, `partial`, `missing`, а также diagnostics по scanned store dirs и `*-partial` blobs. Project storage manifests не считаются installed, если configured runtime не отдаёт модель через `ollama list`.
- `/models/pull` запускается только после явного действия пользователя и подтверждения в UI; normal progress показывается в download-card без success/progress toast и без авто-выбора ещё не установленной модели.
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

1. UI отправляет `POST /chat/tasks`; поле `stream` берётся из profile preference `settings.streaming_enabled`.
2. Backend валидирует profile/session/model.
3. Если модель не выбрана, возвращается readable `chat_model_not_selected` до создания session.
4. Если выбранная chat-модель не установлена, возвращается readable `chat_model_missing`; auto-pull не запускается.
5. Считается `effective_settings = defaults + profile/model overrides`.
6. Подгружается summary memory.
7. Подгружается только short raw history по `mem_turns`.
8. Если включён RAG, выполняется retrieval по активному профилю.
9. Собирается `messages[]`.
10. Backend сохраняет user-message и assistant-message со `status=generating`.
11. Создаётся generation task, который возвращает `task_id`, `user_message_id`, `assistant_message_id`.
12. Запрос отправляется в Ollama OpenAI-compatible endpoint.
13. Если request содержит `stream=true`, ответ финальной answer-модели приходит chunks через native Ollama streaming API, partial content сохраняется в SQLite и отдаётся через SSE `delta`.
14. Если `stream=false` или поле `stream` отсутствует, worker использует full-response fallback без `delta`, очищает ответ через `sanitize_reply()`, сохраняет его в тот же assistant-message и возвращает результат через task polling.

### 3.1. Current task lifecycle limitations

Текущий chat task runtime уже вынесен в отдельные backend task-роуты. SSE endpoint отдаёт lifecycle-события и, при `stream=true`, token delta от финальной answer-модели:

- `backend/apps/chat/routes.py` создаёт chat task через `POST /chat/tasks`;
- `backend/apps/chat/tasks.py` запускает отдельный process, держит runtime-state в памяти и во временных JSON-артефактах внутри `app/data/chat_tasks`;
- публичные task-state сейчас: `generating`, `streaming`, `completed`, `failed`, `cancelled`, `cancelling`;
- backend отдаёт lifecycle stream через `GET /chat/tasks/{task_id}/events`;
- omitted/`stream=false` request не запускает streaming worker path: task остаётся `generating` до полного ответа, затем переходит в `completed` или `failed`;
- UI settings содержит первую Generation-card `Стриминг ответов` во вкладке `Чат / LLM`, сразу сохраняет значение в profile preferences как `streaming_enabled` и передаёт его в `POST /chat/tasks` как `stream`; default для новых/неинициализированных профилей — `true`;
- UI в `web_ui/js/app.js` рендерит assistant-message по persistent `status`;
- при `stream=true` UI подписывается на `GET /chat/tasks/{task_id}/events`, кладёт `delta` в typewriter-buffer, плавно допечатывает assistant-message и возвращается к polling, если SSE-соединение оборвалось;
- non-streaming fallback в UI по-прежнему использует polling `GET /chat/tasks/{task_id}` через `waitForChatTask()`;
- normal chat lifecycle не вызывает toast/footer для start, streaming-progress, completed или autorouter confidence/model-selection; router decision остаётся в `used_settings`/`model_selected`, а user-facing `router_notice` для normal-success routing намеренно пустой;
- при открытии session UI ищет active assistant-message с `task_id`; если task ещё жив, UI восстанавливает SSE/polling наблюдение, а уже сохранённый partial content используется как replay-base, чтобы старые `delta` не добавились повторно;
- optimistic placeholder `Думаю…` больше не используется для assistant generation state;
- SQLite `chat_messages` поддерживает persistent lifecycle fields, а текущий task route уже создаёт assistant-message до запуска answer-модели;
- `GET /sessions/{session_id}/messages` возвращает сохранённые lifecycle-поля, по которым UI восстанавливает visual-state и active generation state;
- если `GET /chat/tasks/{task_id}` или SSE endpoint больше не находит runtime task, backend переводит связанное active assistant-message в `failed`, чтобы пользователь не оставался с вечным `generating`;
- autorouter (`backend/apps/chat/services/model_router.py`) уже выполняется как отдельная lifecycle-стадия до target-model и не отдаёт token delta.

### 3.1.1. Chat task response

`POST /chat/tasks` возвращает backward-compatible task payload:

- `id` / `task_id`: id generation task;
- `session_id` / `conversation_id`: id текущего chat session;
- `user_message_id`: persisted user-message;
- `assistant_message_id`: persisted assistant-message;
- `state`: `generating`, `streaming`, `completed`, `failed`, `cancelled` или transitional `cancelling`;
- `model_name`, `used_settings`, `router_notice`, `warnings`; для normal-success autorouter path `router_notice` пустой, а route-debug данные остаются в `used_settings`;
- `stream` / `streaming_enabled`: включён ли streaming для финальной answer-модели.

Если ошибка возникает после создания session/message state, route возвращает failed task и сохраняет ошибку в assistant-message `error`. Если модель не выбрана вообще, запрос по-прежнему отклоняется до создания session.

### 3.1.2. Chat task lifecycle SSE

`GET /chat/tasks/{task_id}/events` возвращает `text/event-stream` и закрывает соединение после финального события.

Lifecycle events:

- `status`: текущий transitional state, например `generating` или `cancelling`;
- `model_selected`: answer-модель, записанная в task после ручного выбора или autorouter selection;
- `delta`: chunk текста от финальной answer-модели, доступен только если task создан с `stream=true`;
- `done`: финал `{"status":"completed"}`;
- `error`: финал `{"status":"failed","message":"...","code":"..."}`;
- `cancelled`: финал `{"status":"cancelled"}`.

Autorouter не является источником `delta`: route selection выполняется до старта answer-модели и отражается только через metadata/lifecycle.

### 3.1.3. Non-streaming fallback

Fallback остаётся штатным backend path:

- request без `stream` трактуется как `stream=false`;
- `POST /chat/tasks` всё равно создаёт user-message и assistant-message со `status=generating`;
- worker вызывает non-streaming `ChatService.chat_completion()`;
- SSE stream для такого task может отдавать lifecycle events, но не отдаёт `delta`;
- после полного ответа assistant-message получает `content`, `status=completed`, `is_partial=false`;
- при ошибке assistant-message получает `status=failed` и сохранённый `error`.

### 3.1.4. Reconnect / refresh recovery

Recovery строится от persistent message state:

- UI при `openSession()` перечитывает `GET /sessions/{session_id}/messages`;
- если последнее active assistant-message имеет `task_id`, UI запрашивает `GET /chat/tasks/{task_id}`;
- живой streaming task переподписывается на `GET /chat/tasks/{task_id}/events`, non-streaming task продолжает polling;
- SSE может replay-нуть старые `delta`, поэтому `web_ui/js/app.js` сравнивает replay с уже сохранённым partial `message.content` и добавляет только новую часть;
- плавность live-печати регулируется только на UI-слое в `web_ui/js/app.js`: константы `STREAM_TYPEWRITER_INTERVAL_MS`, `STREAM_TYPEWRITER_MIN_CHARS`, `STREAM_TYPEWRITER_MAX_CHARS`, `STREAM_TYPEWRITER_BACKLOG_STEP`, `STREAM_TYPEWRITER_FINAL_FLUSH_CHARS`;
- если task завершился, UI перечитывает messages и показывает финальный `completed` / `failed` / `cancelled`;
- если task не найден, backend помечает связанное active assistant-message как `failed`, а UI перечитывает messages.

### 3.1.5. Verification checklist

Последний verification pass для persistent generation state + SSE проверяет:

- `stream=true`: task payload содержит `stream=true`, SSE отдаёт `delta` и `done`, assistant-message сохраняется как `completed`;
- `stream=false`: task payload содержит `stream=false`, SSE/polling не отдаёт `delta`, assistant-message сохраняет полный ответ как `completed`;
- live Ollama smoke: локальная answer-модель отдаёт реальные SSE `delta`, task завершается `completed`, assistant-message содержит persisted `content` и `task_id`;
- switching/refresh source of truth: `GET /sessions/{session_id}/messages` возвращает active `streaming` assistant-message с `content` и `task_id`;
- stale runtime task: `GET /chat/tasks/{task_id}` переводит связанное active assistant-message в `failed`;
- missing model: user-message сохраняется, assistant-message получает `failed` и readable `error`;
- autorouter: route selection использует non-streaming `chat_completion`, а `stream=true` передаётся только в task финальной answer-модели;
- project smoke: `uvicorn backend.server:app`, `/health` и static UI route стартуют без active LLM-модели;
- hygiene: вне `compare-branch/` нет запрещённого AI-флага и realtime-транспорта.

Metal-to-CPU recovery:

- если native Ollama request падает на Metal backend до выдачи текста, runtime выгружает модель и повторяет запрос;
- если повтор тоже падает на Metal backend, runtime ещё раз выгружает модель перед CPU fallback payload (`num_gpu=0`, `keep_alive=0`);
- для streaming path fallback разрешён только до первого text chunk, чтобы не смешивать два разных ответа в одном assistant-message.

### 3.2. Message lifecycle storage

`chat_messages` расширена без потери истории:

- `status`: `generating`, `streaming`, `completed`, `failed`, `cancelled`;
- `model`: answer-модель, связанная с assistant-message;
- `updated_at`: время последнего изменения content/status;
- `error`: сохранённый текст ошибки для `failed`;
- `generation_started_at` / `generation_finished_at`: timestamps генерации assistant-message;
- `is_partial`: признак незавершённого partial content;
- `task_id`: связь assistant-message с generation task.

Старые сообщения при миграции получают `status=completed`, `is_partial=false`, а `updated_at` backfill-ится из `created_at`. DB helper layer теперь умеет создавать assistant placeholder через `create_assistant_message()`, обновлять lifecycle через `update_message()`, накапливать partial content через `append_message_content()` и искать assistant-message по `task_id`.

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
-> chunking by max_transcript_chars for long inputs
-> selected action route
   clean: cleaner
   summary: summary
   smart_summary: structurer -> merge structured chunks -> summary -> coverage QA
   full: segmenter -> speaker resolver -> structurer -> merge structured chunks -> summary -> coverage QA
-> DB
-> optional chat context / memory
```

API:

- `POST /transcripts/{id}/pipeline`
- `GET /transcripts/{id}/pipeline/latest`
- `PATCH /transcripts/{id}/pipeline/{run_id}/speakers`
- `POST /transcripts/{id}/pipeline/{run_id}/summary`
- `POST /asr/stop` — emergency stop для ASR Studio: отменяет активные transcription tasks, ставит stop flag для pipeline и выгружает активные/default pipeline-модели из Ollama.

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

Default preset для длинных русскоязычных встреч:

| Stage | Model | Temperature | Max tokens |
| --- | --- | ---: | ---: |
| cleaner | `qwen2.5:7b-instruct` | `0` | `9000` |
| segmenter | `qwen2.5:7b-instruct` | `0.05` | `8000` |
| speaker resolver | `qwen2.5:7b-instruct` | `0.1` | `4000` |
| structurer | `qwen3:8b` | `0.1` | `8000` |
| summary | `mistral-nemo:12b` | `0.1` | `8000` |

Whisper defaults для ASR Studio: `large-v3-turbo`, русский prompt/language, `beam_size=5`, `threads=4`. `qwen2.5:3b-instruct` больше не основной качественный вариант для cleaner/segmenter; он остаётся быстрым fallback. User/model overrides из `model_settings.pipeline_json` merge-ятся поверх default pipeline и имеют приоритет.

ASR Studio analysis actions:

| UI mode | Backend action | Route |
| --- | --- | --- |
| `Быстрое саммари` | `summary` | raw transcript -> summary |
| `Умное саммари` | `smart_summary` | raw transcript/chunks -> structurer -> summary |
| `Полный анализ` | `full` | raw transcript/chunks -> segmenter -> speaker resolver -> structurer -> summary |
| manual `Очистить` | `clean` | raw transcript -> cleaner |

Cleaner is optional and is not part of the default summary/smart/full routes. It remains available as a manual stage because repeated speech can be useful evidence rather than noise.

Stage settings have priority over mode routes. If a stage is saved as `enabled=false` via UI `Не использовать`, backend `_stage_enabled` skips it in every action. `smart_summary` falls back to direct summary when `structurer` is disabled and records `smart_summary_structurer_disabled_fallback_summary`; summary-producing actions return `asr_summary_stage_disabled` when `summary` is disabled instead of silently re-enabling it.

`asr.analysis_language` controls ASR analysis output language: `auto` follows the transcript language, while `ru` and `en` force Russian or English. `asr.analysis_prompt` is profile-level context for structurer/summary/retry prompts. These settings do not affect Whisper transcription.

Long transcript handling:

- `max_transcript_chars` в ASR pipeline используется как размер chunk, а не как лимит полного transcript;
- действие `summary` намеренно лёгкое: raw transcript -> summary, без cleaner/speaker/structurer;
- действие `smart_summary` использует chunked structurer merge перед final summary и coverage QA;
- compact segment digest для длинного summary сохраняет начало и конец встречи, а не только prefix;
- полный анализ закрыт profile setting `asr_full_analysis_enabled=false` по умолчанию; UI не даёт запустить `Полный анализ` без явного включения и warning confirmation;
- в полном анализе каждый chunk проходит segmenter/speaker resolver/structurer, если эти stages не выключены пользователем;
- structured outputs merge-ятся в единый `structured_json` с `coverage_topics`, `chunk_summaries` и `chunk_count`;
- summary получает `source_mode=chunked_merge`, merged structure, coverage topics и compact segment digest, а не обрезанный raw transcript prefix;
- warning `raw_transcript_chunked:<N>` означает штатную полную chunked-обработку;
- warning `raw_transcript_truncated` не должен появляться в нормальном summary path; если он возникнет, результат нужно считать неполным;
- summary QA чинит ложный блок `Ключевые решения — не зафиксировано`, когда structured decisions/agreements есть;
- если final summary не покрывает крупные темы, warning `summary_topic_coverage_missing:<N>` запускает retry с `missing_topics`, предыдущим summary и merged evidence;
- успешный retry добавляет диагностический warning `summary_topic_coverage_retry_succeeded`, но только если missing topics раскрыты смыслово, а не упомянуты одним ключевым словом;
- если retry всё ещё пропускает темы, добавляется `summary_topic_coverage_retry_failed:<N>`, а результат явно получает блок `Неполное summary: не удалось покрыть следующие темы`;
- structurer выделяет generic `current_state` и `target_state`, чтобы summary не смешивало текущее устройство процесса/архитектуры с целевой схемой;
- подозрительные ASR-термины технических артефактов не исправляются словарём; summary prompt требует выносить спорные термины в вопросы для уточнения;
- неподтверждённые action-like bullets из `Ключевые решения` переносятся в proposals, если нет явного confirmation marker.

Runtime note: full long chunked runs can perform multiple sequential local LLM calls across segmenter/speaker resolver/structurer plus one summary retry on `mistral-nemo:12b`. This is expected quality work, but it can be thermally expensive on a laptop. Keep full analysis disabled for routine summary-only work, use `stage_timings`, warnings and process checks during manual QA, and do not run repeated live long-meeting tests in parallel with other local LLM/ASR workloads.

ASR stop behavior:

- transcription tasks run in separate processes and can be terminated/killed by task id or through `POST /asr/stop`;
- pipeline requests are synchronous, so `POST /asr/stop` sets an in-memory stop flag checked before/after every LLM stage and unloads active pipeline models from Ollama;
- if the current model call is already inside Ollama, cancellation may become effective after that call returns or fails; the next stage must not start after the stop flag is set;
- UI `Остановить` aborts the active frontend request, calls backend stop, clears busy state and leaves the user in control for manual thermal testing.

Whisper runtime diagnostics:

- фактический запуск whisper.cpp пишется JSONL-строками в `tmp_logs/transcribe.log`;
- лог содержит backend, binary, model/model_path, language, beam_size, threads, prompt metadata, audio conversion metadata и redacted argv command;
- prompt в command не раскрывается: вместо текста пишется `<prompt chars=N>`, отдельно сохраняются только prompt flags и длина;
- `TRANSCRIBE_LOG_MAX_BYTES` ограничивает размер текущего файла, default `2097152`; при превышении текущий файл переезжает в `transcribe.log.1`, хранится только один backup;
- `TRANSCRIBE_LOG_MAX_BYTES=0` отключает запись diagnostics.

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
- `streaming_enabled` (profile runtime setting, default `true`);
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
- cleaner: `0`;
- segmenter: `0.05`;
- speaker resolver: `0.1`;
- structurer: `0.1`;
- summary: `0.1`;
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
- `tmp_logs/pipeline.log`;
- `tmp_logs/transcribe.log`.

Pipeline log содержит stage, elapsed time, input/output sizes, errors, truncation flag и used settings.

## 11. LAN

Основной launcher:

- `start_localgpt_lan.sh`;
- `start_localgpt_lan.command`.

Legacy alias:

- `LTrnsrb.command`.

LAN launcher стартует backend с предпочтением `127.0.0.1:<LOCALGPT_PORT>`, но если порт занят, выбирает следующий свободный локальный порт; Caddy остаётся на `https://<lan-ip>:<LAN_HTTPS_PORT>` и проксирует на фактический backend-порт.
Определение LAN IP предпочитает Wi-Fi/private IPv4 (`192.168.*`, `10.*`, `172.16-31.*`), чтобы не отдавать VPN/Tailscale IP телефону в обычной Wi-Fi сети.

Диагностика/фикс LAN runtime:

- `run_localgpt.py` читает `LOCALGPT_HOST` и `LOCALGPT_PORT` из `.env`, defaults остаются безопасными: `127.0.0.1:8000`;
- `tools/LTrnsrb.sh` читает `LOCALGPT_PORT`, legacy `LOCALGPT_BACKEND_PORT`, `LAN_HTTPS_PORT` и `LOCALGPT_LAN_HTTPS_PORT` из shell env или `.env`;
- если backend уже жив на `127.0.0.1:<LOCALGPT_PORT>`, LAN launcher переиспользует его и не стартует второй backend;
- если backend уже жив на соседнем auto-selected порту (`8000..8099`), LAN launcher обнаруживает его через `/health` и проксирует Caddy на фактический порт;
- фактический backend port пишется в runtime-файл и используется при генерации Caddy config;
- Caddy config включает один актуальный upstream `127.0.0.1:<detected-port>` с retry и `flush_interval -1`, поэтому streaming/SSE не буферизуется reverse proxy;
- Caddy стартует через user LaunchAgent `local.localgpt.caddy`, чтобы `LAN_HTTPS_PORT` оставался слушать после выхода wrapper-скрипта;
- Caddy config генерируется под текущий LAN IP во временной runtime-директории, а корневой `Caddyfile.lan` остаётся fallback-примером;
- `/health.lan_url` возвращается только если LAN HTTPS port реально слушает, чтобы UI не предлагал мёртвый LAN URL;
- локальный backend-port и LAN proxy-port разделены: `http://127.0.0.1:8002/...` может быть текущим локальным UI, но телефон всё равно идёт через `https://<lan-ip>:8443/...`;
- UI использует same-origin API (`window.location.origin` / relative paths), поэтому polling `/chat/tasks` и остальные API работают за reverse proxy без отдельного CORS;
- CORS default больше не `*`: backend разрешает local/private-origin regex (`localhost`, LAN RFC1918, Tailscale CGNAT `100.64.0.0/10`, `.local`), а дополнительные origins задаются через `LOCALGPT_CORS_ALLOW_ORIGINS`.

## 12. Plugin Registry and remote address providers

Plugin Registry v0 живёт в `backend/apps/plugins/` и намеренно не является произвольным extension runtime.

Current API:

- `GET /plugins`;
- `POST /plugins/{plugin_id}/enabled`;
- `GET /plugins/network-addresses`.

Trust model:

- registry читает только `plugins/*/plugin.json`;
- plugin folders являются metadata/docs-only;
- код из `plugins/` не импортируется и не исполняется;
- unknown plugin ids показываются как untrusted и не могут стать effectively enabled;
- plugins disabled by default;
- trusted behavior реализуется только backend-owned handlers под `backend/apps/plugins/`.

Tailscale official/internal plugin:

- metadata/docs: `plugins/tailscale/`;
- trusted handler: `backend/apps/plugins/tailscale.py`;
- handler делает только read-only checks: CLI presence, `tailscale status --json`, `tailscale serve status --json`;
- handler отдаёт manual command text, но не запускает `tailscale serve`;
- Funnel/public exposure/router ports не включаются.

Network address provider contract:

- core LAN provider отдаёт item из существующего LAN URL helper только когда адрес реально доступен;
- trusted plugin handlers могут добавлять адреса только если plugin trusted/enabled и handler подтверждает availability;
- frontend не синтезирует Tailscale URL, а копирует только backend-provided `items`;
- topbar fast path: 0 адресов — disabled/warning, 1 адрес — left-click copy, 2+ адреса — left-click menu.

Security statements for Tailscale mode:

```text
Do not expose LocalGPT directly to the public internet.
Do not enable Tailscale Funnel unless you fully understand the risk.
Preferred mode: Tailscale private tailnet only.
```

## 13. Static UI system

Основной UI — `web_ui/gui_html.html` + `web_ui/js/app.js` + `web_ui/css/style.css`.

Текущий UI v2:

- floating topbar с blur, мягкой тенью и без жёсткого нижнего разделителя;
- sidebar с glass/blur-слоем и collapsible state;
- `localStorage.sidebar_open` хранит состояние sidebar;
- `Cmd+B` / `Ctrl+B` переключает sidebar;
- toast-система отображает уведомления строго под topbar по центру;
- нижняя composer-зона не содержит системных статусов;
- icon-only RAG topbar button показывает состояние активного профиля: OFF без dot/glow, ON с фиолетовым dot и glow;
- topbar network address button копирует один backend-provided address сразу или открывает меню выбора для LAN/Tailscale адресов;
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

## 14. Git/runtime hygiene

В git не должны попадать:

- `.env`;
- SQLite DB;
- chat/asr/tts task JSON;
- logs;
- model files and caches;
- profile RAG contents.

В git оставляется только структура (`.gitkeep`) и документация (`rag_sources/README.md`).

## 15. Test coverage

Текущие ключевые проверки:

- empty Ollama model list не запускает auto-pull;
- chat task без выбранной модели возвращает `chat_model_not_selected` и не создаёт session;
- readable `chat_model_missing`;
- LLM model-state reconciliation: runtime-installed model remains installed even if an orphan `*-partial` blob exists in another store; missing runtime model with matching partial is reported as `partial`;
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
