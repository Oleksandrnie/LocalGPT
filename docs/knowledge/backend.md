# Backend

## Структура

Активный FastAPI app собирается в `backend/server.py`.

```text
backend/
├── server.py
└── apps/
    ├── chat/
    ├── asr/
    ├── tts/
    ├── ocr/
    ├── rag/
    └── plugins/

app/
├── config.py
├── db.py
├── roles.py
├── routes/
├── schemas/
└── services/
```

`backend/apps/` — feature layer. `app/` — shared и transitional layer. `app/server.py` только re-export-ит активный app.

## Request lifecycle

1. Uvicorn загружает `backend.server:app`.
2. При импорте инициализируется SQLite через `db.init_db()` и логируется конфигурация.
3. `backend/server.py` подключает shared routers из `app/routes/` и feature routers из `backend/apps/`.
4. CORS использует explicit origins и private/local regex из `app/config.py`.
5. Static UI монтируется на `/ui`; cache для `/ui/*` принудительно отключён.

## Feature boundaries

| Feature | Основные файлы | Ответственность |
| --- | --- | --- |
| Chat | `backend/apps/chat/routes.py`, `attachments.py`, `service.py`, `tasks.py`, `services/` | request preparation, image attachments, text/vision routing, Ollama, persisted tasks/SSE |
| ASR | `backend/apps/asr/routes.py`, `pipeline.py`, `transcripts.py`, `whisper*.py` | transcription, history, model management, analysis pipeline |
| TTS | `backend/apps/tts/router.py`, `service.py`, `providers/` | provider abstraction, generation, voice library, history |
| OCR | `backend/apps/ocr/routes.py`, `service.py` | image OCR и cleanup |
| RAG | `backend/apps/rag/routes.py`, `service.py` | sources, ingest, chunks, retrieval, context |
| Plugins | `backend/apps/plugins/registry.py`, `routes.py`, `tailscale.py` | manifests, trust, state, docs и backend-owned handlers |

Shared routers:

- `app/routes/meta.py` — health, version, runtime shutdown/restart, DB cleanup/reset;
- `app/routes/models.py` — model catalog, pull/preload/download state;
- `app/routes/profiles.py` — profiles, sessions, messages и model settings;
- `app/routes/storage.py` — model/storage path settings;
- `app/routes/criteria.py` — criteria parsing.

Chat attachment HTTP boundary:

- `POST /chat/attachments` — profile-owned upload и preprocessing PNG/JPEG/WebP;
- `GET /chat/attachments` — session/message attachment metadata;
- `GET /chat/attachments/{id}` и `/thumbnail` — ownership-checked media;
- `DELETE /chat/attachments/{id}` — удаление неактивного attachment;
- `GET /chat/attachments/cache` и `POST /chat/attachments/cleanup` — статистика и явная очистка cache.

`POST /chat/tasks` принимает только attachment ids. Router до запуска worker проверяет profile/session ownership, status, count и общий размер, связывает записи с единственным persisted user message/task и передаёт task-safe descriptors без публикации filesystem paths.

Chat runtime возвращает reasoning и final content раздельно. Worker публикует SSE `delta` и накапливает `chat_messages.content` только из final content; reasoning сохраняется отдельно и доступен через `GET /chat/messages/{message_id}/reasoning?profile_id=...` после проверки profile/session ownership. Обычный history endpoint возвращает только `has_reasoning`, поэтому reasoning не участвует в следующем prompt.

## API boundaries

Routers отвечают за HTTP validation/serialization и вызывают service/repository functions. Бизнес-логика не должна переноситься в `backend/server.py`.

Новые endpoints:

1. объявляются в router своего feature;
2. используют schema вместо неструктурированного dict, если contract нетривиален;
3. не обращаются к `compare-branch/`;
4. не исполняют код из plugin directories;
5. сохраняют profile isolation для sessions, RAG и settings.

## Database

`app/db.py` управляет schema и migrations без внешнего migration framework. Основные таблицы:

- `profiles`, `chat_sessions`, `chat_messages`, `chat_attachments`;
- `transcripts`, `transcript_pipeline_runs`, `session_summaries`;
- `model_settings`, `app_settings`;
- `source_documents`, `document_chunks`, `document_embeddings`.

Repository functions возвращают обычные dict. Runtime path берётся из `LOCALGPT_DB_PATH` или `app/db/localgpt.db`.

Message lifecycle поля включают `status`, `model`, `error`, `task_id`, timestamps, `is_partial` и отдельное bounded поле `reasoning`. Legacy rows мигрируют в завершённое состояние. Model settings хранят `output_tokens` и `thinking_tokens`; legacy `max_tokens` мигрирует как output budget и остаётся compatibility alias.

`chat_attachments` хранит ownership, MIME/dimensions/size, backend-owned относительные storage/thumbnail paths, связи с message/task и lifecycle status. Binary/base64 не пишутся в таблицу или message content.

## Tasks и cancellation

Chat, transcription и TTS имеют in-process task registries. Runtime shutdown/reset сначала отменяет активные tasks. Эти registries не являются durable queue: после process loss backend восстанавливает пользовательское состояние через persisted records и reconciliation rules, а не продолжает Python thread. Для image chat reconciliation также переводит незавершённые attachment records в terminal failed/cancelled state; cleanup не удаляет attachment активной задачи.

Model export также использует process-local task registry: start, status/cancel и ready-only download. Import upload получает opaque `upload_id`; confirm endpoint повторно валидирует bundle перед записью. Browser не передаёт destination/source paths. Terminal import/discard удаляет upload archive; `GET`/`DELETE /model-transfer/uploads` соответственно показывают usage и очищают только direct regular `.localgpt-models` files из backend-owned upload directory, одновременно инвалидируя их opaque IDs.

## Добавление модуля

- Создать `backend/apps/<feature>/` с `__init__.py`, router и service boundaries.
- Подключить router в `backend/server.py`.
- Shared код добавлять в `app/` только если он действительно используется несколькими features; иначе держать рядом с feature.
- Добавить unit/API tests в `tests/`.
- Обновить только затронутые разделы [ARCHITECTURE.md](../ARCHITECTURE.md), [TESTING.md](../TESTING.md) и соответствующий knowledge-файл.

## Ограничения

- Layout transitional: `app/` ещё не чистый core.
- Task registries process-local.
- SQLite синхронный и рассчитан на локальный single-runtime сценарий.
- Активный UI и часть backend логики остаются крупными файлами.
