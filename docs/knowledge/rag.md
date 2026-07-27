# RAG

## Source layout

RAG изолирован по профилям:

```text
rag_sources/
├── README.md
└── profile-<id>/
    ├── document.md
    └── document.json
```

`rag_sources/README.md` — component-owned инструкция. Остальные файлы runtime-only и игнорируются Git.

Поддерживаются `.txt`, `.md` и `.json`. Path resolution запрещает выход из profile source directory.

## Ingestion

`backend/apps/rag/service.py`:

1. создаёт/находит directory профиля;
2. сканирует поддерживаемые файлы;
3. для Markdown при необходимости создаёт structured JSON companion;
4. читает и нормализует текст;
5. создаёт chunks;
6. считает embeddings;
7. синхронизирует `source_documents`, `document_chunks`, `document_embeddings`;
8. удаляет stale records.

Upload endpoint сохраняет файлы только после suffix/path validation. Force ingest пересобирает structured companions и index.

## Markdown и structured JSON

Markdown parser выделяет headings/sections и отдельные pricing/constraint facts. Generated JSON хранит структурированное представление рядом с source Markdown. Это облегчает точный retrieval, но Markdown остаётся читаемым source.

Ручной JSON полезен, когда данные имеют строгую схему или неоднозначные числовые условия. Требования к содержимому source files описаны в [`rag_sources/README.md`](../../rag_sources/README.md).

## Chunking

Текущие constants:

- `CHUNK_CHARS = 1200`;
- `CHUNK_OVERLAP = 180`.

Service старается резать по абзацам, а длинные блоки — по окнам с overlap. Metadata связывает chunk с profile, source id/type, position и embedding model.

## Embeddings и search

`EMBEDDING_MODEL = local-hash-v1` — deterministic local hashing vector, не внешняя neural embedding model. Индексация не требует Ollama и не загружает chat LLM.

Search:

1. строит embedding запроса;
2. загружает embeddings только активного профиля и текущей model id;
3. вычисляет cosine similarity;
4. сортирует по score;
5. возвращает top-k;
6. `build_context()` собирает блок до `max_chars`.

Это лёгкий локальный retrieval. Semantic quality ограничена hashing approach; точные headings, ключевые слова и structured facts особенно важны.

## Chat integration

`backend/apps/chat/routes.py` проверяет effective `rag_enabled`, собирает query из недавних user queries и текущего сообщения, вызывает `search()` и `build_context()`.

`backend/apps/chat/service.py` добавляет RAG как authoritative local system context после profile/memory blocks. Если данных недостаточно, prompt запрещает выдумывать отсутствующие факты.

Настройки профиля определяют:

- `rag_enabled`;
- `rag_top_k`;
- `rag_max_context_chars`.

## ASR context

Transcript с `labels.origin=asr_context` индексируется как отдельный source type:

- source id связан с transcript id;
- status возвращает contexts отдельно от обычных files;
- удаление context удаляет RAG records и связанную transcript entry;
- удаление transcript очищает его context index.

Это отличается от сохранения текстового файла в profile folder.

## Storage

SQLite:

- `source_documents` — source metadata;
- `document_chunks` — text и position;
- `document_embeddings` — vector JSON/model id.

Profile deletion/reset удаляет profile source directory и DB records. Git не является хранилищем пользовательского RAG.

## Reindexing

Перезапустите ingest, если:

- source изменён;
- generated JSON устарел;
- chunking/embedding model изменились;
- status показывает mismatch/stale record;
- retrieval не находит новый документ.

Force ingest нужен только для намеренной полной перестройки. Перед ним сохраните важные runtime sources.

## Типовые ошибки

- unsupported suffix;
- пустой или выходящий за source root path;
- пустой ASR context;
- отсутствующий context/file при удалении;
- выбран неправильный profile;
- RAG выключен в effective settings;
- слишком маленький `max_context_chars`;
- слабое совпадение из-за hashing embeddings и нечётких source terms.

## Проверки качества

- profile isolation;
- число sources/chunks;
- deterministic search на известной marker строке;
- presence в debug prompt;
- delete/reindex cleanup;
- сравнение source metadata с profile directory.

Команды: [TESTING.md](../TESTING.md).
