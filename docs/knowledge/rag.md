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

Embedding слой имеет versioned provider contract. Compatibility generation `local-hash-v1` остаётся default и не требует Ollama; semantic generation использует локальный Ollama `/api/embed` с `embeddinggemma:latest`, фиксированными model version и dimensions. Канонический generation key включает provider/model/version/dimensions, а те же поля сохраняются в metadata документа и vector row. Векторы разных generation не смешиваются.

Semantic provider передаёт `truncate=false`, валидирует число, размерность и конечность значений и не откатывается молча к hashing при timeout, отсутствии модели или несовместимом ответе. Последний batch отправляется с `keep_alive=0`, поэтому embedding model предсказуемо выгружается; промежуточные reindex batches используют bounded keep-alive. Размер batch ограничен настройкой.

Переключение `RAG_EMBEDDING_PROVIDER`/model/version/dimensions не конвертирует индекс автоматически: search возвращает `rag_embedding_reindex_required`, пока все доступные chunks не получат выбранное generation. Переиндексация сначала полностью рассчитывает новое поколение и только затем атомарно публикует его; если source chunks изменились во время расчёта, публикация отклоняется с `rag_embedding_source_changed`, а прежнее generation остаётся целым. Сохранённые generations позволяют выполнить rollback возвратом прежней конфигурации без повторного чтения corpus.

`GET /rag/status` сообщает configured descriptor, `total_chunks`, `indexed_chunks`, `missing_chunks`, `pending_sources` и metadata доступных generations. Состояния имеют чёткий порядок: invalid provider configuration → `configuration_error`; новые/изменённые Markdown sources → `ingest_required`; отсутствующее configured generation → `reindex_required`; совпадающий source/index → `ready`. Absolute paths и raw exception text наружу не передаются.

Semantic reindex запускается только явно через `POST /rag/reindex`; UI перед запуском показывает модель, объём chunks и предупреждение о локальной нагрузке. На весь backend допускается одна background operation, прогресс читается через profile-owned `GET /rag/reindex/{task_id}`. Task state process-local, поэтому после рестарта незавершённая operation исчезает, а UI повторно получает канонический generation state из SQLite. Это не silent download/reindex: установка модели и обычный ingest sources остаются отдельными действиями.

Default search strategy `hybrid_v2`:

1. делит multi-part query максимум на восемь bounded facets;
2. загружает только matching embedding generation и только разрешённые profile/session chunks; assistant-authored Chat exports исключаются из factual evidence;
3. независимо строит bounded lexical pool по BM25-style score/token coverage и semantic pool по cosine similarity;
4. не создаёт semantic pool для `local-hash-v1`, потому что hashing collision не является семантическим доказательством;
5. объединяет ranks через `rrf_v1`, сохраняя lexical/semantic ranks и pool membership в provenance diagnostics;
6. допускает semantic-only candidate без буквального overlap, но отмечает facet поддержанным только при более строгом semantic threshold;
7. штрафует повторяющийся boilerplate и сначала выбирает разные источники, покрывающие разные facets;
8. отдельно оценивает facets как `supported`, `partial`, `conflict` или `not_found` и прикладывает короткие evidence spans;
9. `build_context()` сначала сжимает слишком объёмную diagnostics до facet/status metadata, затем делит оставшийся `max_chars` между всеми selected chunks; длинный первый фрагмент не может вытеснить остальные доказательства.

Production ranking не содержит CMS/company/brand vocabulary или отдельного capability bonus. Conflict diagnostics связывает год с тем же chunk, где найдено exclusive/alternative утверждение, чтобы случайные годы из соседнего boilerplate не создавали ложный конфликт.

Пока выбран compatibility generation, semantic quality ограничена hashing/lexical approach; точные headings, ключевые слова и structured facts особенно важны. Semantic provider уже доступен как инфраструктура, но не включается автоматически и не загружает модель без явной локальной установки и переиндексации.

Контролируемая локальная проверка `embeddinggemma:latest` подтвердила полный explicit reindex 2,925/2,925 chunks, `hybrid_v2` semantic retrieval и освобождение embedding-модели после операции. Один и тот же bounded retrieval snapshot затем передавался строго последовательно Qwen 2.5 3B Instruct, Qwen 2.5 7B Instruct и Qwen 3 4B с выгрузкой между вызовами. Все ответы остались grounded и не вывели reasoning при Thinking OFF; 3B/7B использовали лишь 2/4 доступных evidence entities, а 4B — 4/4. Это различие относится к model answer completeness, а не к retrieval, и не оправдывает corpus-specific production rules.

На synthetic CMS + regions corpus baseline `legacy` дважды выбирал `duplicate-aggregate.md` в top-2. `hybrid_v2` без специальной CMS-эвристики выбирает отдельные CMS и regions sources через ordinary lexical/facet relevance и source diversity. Старое наблюдение времени для `hybrid_v1` относится только к предыдущей реализации и не является production benchmark.

Отдельный cross-domain eval находится в `tools/rag_retrieval_eval.py` и `tests/fixtures/rag_retrieval_eval/`. Он использует unrelated synthetic domains, exact/paraphrase/typo/conflict/negative cases и metadata-only report. Помимо recall/MRR/grounding, report измеряет binary-relevance `ndcg_at_k` и `ideal_ranked_hit_rate`, поэтому присутствие источника в top-k отделено от его позиции. Это канонический quality gate для будущих embeddings/reranking; временный пользовательский corpus в fixtures и production heuristics не переносится.

Optional reranker не включён в runtime: deterministic semantic `hybrid_v2` уже достигает `ndcg_at_k=1.0` и `ideal_ranked_hit_rate=1.0` на всей текущей cross-domain разметке при сохранении perfect negative/conflict controls. На таком наборе дополнительное переупорядочивание не может доказать прирост, поэтому новая модель/dependency и её resource cost не оправданы. Решение пересматривается только после появления более широкой domain-independent judged выборки или live-provider evidence с неидеальным top-N; пользовательский corpus не используется как tuning set.

Retrieval-strategy rollback не переиндексирует и не меняет источники: app setting `rag_retrieval_strategy=lexical_v1` сохраняет текущие ownership/diversity/diagnostics contracts, но не вызывает semantic query. `legacy` возвращает прежнее ранжирование только для compatibility diagnosis; отсутствие/неизвестное значение выбирает `hybrid_v2`, а сохранённое `hybrid_v1` мигрирует к нему в памяти. Embedding-generation rollback независимо выбирает сохранённый прежний provider/model/version/dimensions key.

## Chat integration

`backend/apps/chat/routes.py` проверяет effective `rag_enabled`, собирает query из текущего сообщения и максимум трёх недавних релевантных user queries: явная тема удерживает только историю с общими meaningful terms, а короткое/deictic уточнение получает последний turn. Повторы удаляются без изменения текста; затем вызываются `search_with_diagnostics()` и `build_context_snapshot()`.

`backend/apps/chat/service.py` добавляет найденные chunks как current authorized evidence, но сериализует их в structured L4 data envelope с ролью `user`, а не как instruction-bearing `system` content. Context builder возвращает одновременно bounded `rag_context` и structured manifest точных content spans/provenance только для chunks, реально вошедших в prompt; этот snapshot передаётся фактическому sync/task completion path. Данные могут подтверждать факты ответа, но instruction-shaped текст внутри источника не меняет policy, persona, задачу или permissions. Assistant history и assistant-authored Chat exports остаются continuity context и не считаются подтверждением факта без актуального источника. Facet diagnostics требуют ответить на подтверждённую часть, явно отметить `not_found`/partial coverage и не выбирать молча при конфликте. Post-answer `rag_answer_diagnostics` сравнивает ответ только с manifest content, реально переданным модели, а не с facet status, rules, filename, diagnostic query или omitted chunk. Поэтому эвристический `not_found` при непустом manifest остаётся отличим от отсутствия evidence: lexical overlap даёт `evidence_traceable`, отсутствие overlap — `evidence_found_answer_not_traceable`. Это требует quality review и не является semantic proof.

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

Нажмите «Индексировать файлы», если:

- source изменён;
- generated JSON устарел;
- status показывает mismatch/stale record;
- retrieval не находит новый документ.

После ingest нажмите «Переиндексировать», только если status показывает `reindex_required`: это создаёт configured embedding generation для всех profile chunks. Изменение provider/model/version/dimensions требует semantic reindex, но не force ingest. При `configuration_error` сначала исправьте локальную конфигурацию; при `rag_embedding_source_changed` дождитесь завершения source-изменений и повторите операцию. Force ingest нужен только для намеренной полной перестройки sources. Перед ним сохраните важные runtime sources.

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
