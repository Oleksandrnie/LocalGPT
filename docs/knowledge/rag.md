# RAG

## Source layout

RAG изолирован по профилям:

```text
rag_sources/
├── README.md
└── profile-<id>/
    └── document.md
```

`rag_sources/README.md` — component-owned инструкция. Остальные файлы runtime-only и игнорируются Git.

Поддерживается только `.md`. Path resolution запрещает выход из profile source directory.

## Ingestion

`backend/apps/rag/service.py`:

1. создаёт/находит directory профиля;
2. сканирует поддерживаемые файлы;
3. читает и нормализует Markdown;
4. создаёт chunks;
5. считает embeddings;
6. синхронизирует `source_documents`, `document_chunks`, `document_embeddings`;
7. удаляет stale records, включая прежние JSON-записи индекса.

Upload endpoint сохраняет только Markdown после suffix/path validation. Один запрос ограничен 12 файлами, 5 MiB на файл и 20 MiB суммарно; чтение bounded, а при превышении лимита ни один файл запроса не публикуется. Force ingest пересобирает index, но не удаляет legacy JSON-файлы с диска.

## Markdown sources

Каждый RAG-документ — один Markdown-файл и один индексируемый источник. Это исключает повторение тех же фактов в retrieval и оставляет пользователю единую редактируемую версию. Точные числа, правила и таблицы записывайте в Markdown явно: с заголовками, списками и короткими строками «поле: значение».

Для цен и расчётов источник должен явно закреплять формат каждой применимой валюты: рубли — `119 600 ₽` и `2 990 ₽/ч`; доллары США — `$500` и `$1,250`; евро — `€300` и `€1,250`. В коммерческих шаблонах символ валюты должен быть частью значения, а не дописываться как `руб.` или другой текст. Случайные или повреждённые символы валюты недопустимы.

Старые JSON-файлы не индексируются и не удаляются автоматически; при необходимости перенесите их содержимое в соответствующий Markdown-файл, затем нажмите «Индексировать». Подробные требования к содержимому описаны в [`rag_sources/README.md`](../../rag_sources/README.md).

## Chunking

Текущие constants:

- `CHUNK_CHARS = 1200`;
- `CHUNK_OVERLAP = 180`.

Service старается резать по абзацам, а длинные блоки — по окнам с overlap. Metadata связывает chunk с profile, source id/type, position и embedding model.

## Embeddings и search

`EMBEDDING_MODEL = local-hash-v1` — deterministic local hashing vector, не внешняя neural embedding model. Индексация и retrieval не требуют Ollama, не загружают chat LLM и не отправляют corpus наружу.

Default search strategy `hybrid_v1`:

1. делит multi-part query максимум на восемь bounded facets;
2. загружает chunks/embeddings только активного профиля и `local-hash-v1`;
3. объединяет cosine score с BM25-style lexical score и inflection-tolerant token coverage;
4. штрафует повторяющийся boilerplate и сначала выбирает разные источники, покрывающие разные facets;
5. исключает assistant-authored Chat exports из factual evidence;
6. возвращает top-k chunks с source/chunk provenance и внутренними score components;
7. отдельно оценивает facets как `supported`, `partial`, `conflict` или `not_found` и прикладывает короткие evidence spans;
8. `build_context()` укладывает diagnostics и selected chunks в `max_chars`.

Это лёгкий локальный retrieval. Semantic quality всё ещё ограничена hashing/lexical approach; точные headings, ключевые слова и structured facts особенно важны. Локальная semantic embedding dependency была рассмотрена, но не выбрана: в текущей среде она требует отсутствующую модель/dependency и отдельную тяжёлую загрузку, поэтому не удовлетворяет offline reproducibility/resource gate этого этапа.

На synthetic CMS + regions corpus baseline `legacy` дважды выбирал `duplicate-aggregate.md` в top-2. `hybrid_v1` выбрал `cms.md` и `regions.md`, снизив top-2 duplicate-source ratio с 100% до 0% и дав specific facet coverage 2/2 вместо 0/2. Один bounded прогон по 100 запросов показал около 3.14 ms/query и 1.56 MB peak для legacy против 10.59 ms/query и 2.16 MB peak для hybrid; это regression-test observation, не production benchmark.

Rollback не переиндексирует и не меняет источники: app setting `rag_retrieval_strategy=legacy` возвращает прежнее ранжирование; отсутствие/неизвестное значение выбирает `hybrid_v1`.

## Chat integration

`backend/apps/chat/routes.py` проверяет effective `rag_enabled`, собирает query из недавних user queries и текущего сообщения, вызывает `search()` и `build_context()`.

`backend/apps/chat/service.py` добавляет найденные chunks как current authorized evidence, но сериализует их в structured L4 data envelope с ролью `user`, а не как instruction-bearing `system` content. Данные могут подтверждать факты ответа, но instruction-shaped текст внутри источника не меняет policy, persona, задачу или permissions. Assistant history и assistant-authored Chat exports остаются continuity context и не считаются подтверждением факта без актуального источника. Facet diagnostics требуют ответить на подтверждённую часть, явно отметить `not_found`/partial coverage и не выбирать молча при конфликте.

Настройки профиля определяют:

- `rag_enabled`;
- `rag_top_k`;
- `rag_max_context_chars`.

HTTP search ограничивает query 16 000 символами и `top_k` диапазоном 1–20; profile/model settings дополнительно ограничивают RAG context budget.

Retrieval имеет два независимых ownership scope:

- Markdown files из `rag_sources/profile-<id>/` являются явно profile-wide;
- `chat_context`, `vision_context` и `asr_context` сохраняют `profile_id + session_id` и доступны только исходной session.

Запрос без `session_id` возвращает только profile-wide sources. Derived row с отсутствующим/неоднозначным legacy `session_id` сохраняется в SQLite, но исключается из chat retrieval вместо неявного расширения scope. Promotion derived content в profile-wide RAG не реализован; для общего знания пользователь создаёт/редактирует обычный Markdown source отдельно.

## ASR context

Transcript с `labels.origin=asr_context` индексируется как отдельный session-owned source type:

- source id связан с transcript id;
- status возвращает contexts отдельно от обычных files;
- удаление context удаляет RAG records и связанную transcript entry;
- удаление transcript очищает его context index.

Это отличается от сохранения текстового файла в profile folder.

## Vision context

Завершённый image chat сам по себе не изменяет RAG. `POST /rag/vision-contexts` создаёт `vision_context` только после явного действия пользователя и проверяет, что profile, session, user message и связанные attachments принадлежат одному scope.

В index передаётся редактируемый производный текст размером до 100 000 символов. Metadata может содержать только безопасные references (`message_id`, `session_id`, `attachment_ids`) и отмечает source как `derived_context`; base64 data URI отклоняется, image files и backend storage paths не копируются. Удаление `vision_context` независимо от chat attachment и не удаляет исходное изображение.

## Chat context

`POST /rag/chat-contexts` явно индексирует отредактированный текст непустого user message или completed assistant message как `chat_context`. Endpoint проверяет active profile, session/message ownership, допустимую роль и terminal status assistant; failed, cancelled или незавершённый assistant не принимается.

Metadata содержит `message_id`, `session_id`, `message_role`, `origin=explicit_chat_export` и `source_role=derived_context`. Reasoning не читается из message row и помечен как не индексированный; binary data URI запрещён. Каждый message имеет независимый `chat-message:<id>` source, который можно удалить через общий context endpoint без удаления сообщения или соседнего source.

## Storage

SQLite:

- `source_documents` — source metadata;
- `document_chunks` — text и position;
- `document_embeddings` — vector JSON/model id.

Session deletion удаляет принадлежащие ей derived documents/chunks/embeddings, но не profile-wide Markdown и не соседние sessions. Profile deletion/reset удаляет profile source directory и все дочерние DB records. Git не является хранилищем пользовательского RAG.

## Reindexing

Перезапустите ingest, если:

- source изменён;
- generated JSON устарел;
- chunking/embedding model изменились;
- status показывает mismatch/stale record;
- retrieval не находит новый документ.

Force ingest нужен только для намеренной полной перестройки. Перед ним сохраните важные runtime sources.

## Corpus hygiene audit

`GET /rag/audit?profile_id=<id>` формирует preview-only metadata report: exact/near duplicate ratio, repeated boilerplate, oversized sources, missing headings, stale dated sources, potential conflicts и suspicious instruction-like content. Report содержит source ids/counts, но не копирует payload фрагменты и выполняет `mutations_performed=0`. Он не является абсолютным injection detector и не удаляет/редактирует пользовательские файлы.

## Типовые ошибки

- unsupported suffix;
- пустой или выходящий за source root path;
- пустой ASR context;
- пустой, несвязанный или содержащий image data URI Vision context;
- пустой/несвязанный Chat context или незавершённый assistant message;
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
- explicit Vision export и независимое удаление text source без изменения attachment;
- explicit user/completed-assistant Chat export, role metadata, reasoning exclusion, retrieval и независимое удаление;
- сравнение source metadata с profile directory.

Команды: [TESTING.md](../TESTING.md).
