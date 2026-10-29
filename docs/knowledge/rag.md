# RAG

## Source layout

RAG изолирован по профилям:

```text
rag_sources/
└── profile_<id>_<name>/
    └── document.md
```

Profile directories создаются приложением по мере необходимости. RAG-файлы являются runtime data и не должны попадать в Git.

Поддерживаются `.md` и Telegram Desktop `.html` (произвольные веб-страницы не принимаются). Path resolution запрещает выход из profile source directory.

## Ingestion

`backend/apps/rag/service.py`:

1. создаёт/находит directory профиля;
2. сканирует поддерживаемые файлы;
3. читает Markdown либо разбирает сообщения Telegram HTML;
4. создаёт chunks;
5. считает embeddings;
6. синхронизирует `source_documents`, `document_chunks`, `document_embeddings`;
7. удаляет stale records, включая прежние JSON-записи индекса.

Upload endpoint сохраняет только Markdown после suffix/path validation. Один запрос ограничен 12 файлами, 5 MiB на файл и 20 MiB суммарно; чтение bounded, а при превышении лимита ни один файл запроса не публикуется. Force ingest пересобирает index, но не удаляет legacy JSON-файлы с диска.

## Markdown sources

Каждый RAG-документ — один Markdown-файл и один индексируемый источник. Это исключает повторение тех же фактов в retrieval и оставляет пользователю единую редактируемую версию. Точные числа, правила и таблицы записывайте в Markdown явно: с заголовками, списками и короткими строками «поле: значение».

Для цен и расчётов источник должен явно закреплять формат каждой применимой валюты: рубли — `119 600 ₽` и `2 990 ₽/ч`; доллары США — `$500` и `$1,250`; евро — `€300` и `€1,250`. В коммерческих шаблонах символ валюты должен быть частью значения, а не дописываться как `руб.` или другой текст. Случайные или повреждённые символы валюты недопустимы.

Старые JSON-файлы не индексируются и не удаляются автоматически; при необходимости перенесите их содержимое в соответствующий Markdown-файл, затем нажмите «Индексировать».

## Chunking

Текущие constants:

- `CHUNK_CHARS = 1200`;
- `CHUNK_OVERLAP = 180`.

Service старается резать по абзацам, а длинные блоки — по окнам с overlap. Metadata связывает chunk с profile, source id/type, position и embedding model.

## Embeddings и search

Embedding слой имеет versioned provider contract. Compatibility generation `local-hash-v1` остаётся default и не требует Ollama; semantic generation использует локальный Ollama `/api/embed` с `embeddinggemma:latest`, фиксированными model version и dimensions. Канонический generation key включает provider/model/version/dimensions, а те же поля сохраняются в metadata документа и vector row. Векторы разных generation не смешиваются.

Semantic provider передаёт `truncate=false`, валидирует число, размерность и конечность значений и не откатывается молча к hashing при timeout, отсутствии модели или несовместимом ответе. Последний batch отправляется с `keep_alive=0`, поэтому embedding model предсказуемо выгружается; промежуточные reindex batches используют bounded keep-alive. Размер batch ограничен настройкой.

Переключение `RAG_EMBEDDING_PROVIDER`/model/version/dimensions не конвертирует индекс автоматически: search возвращает `rag_embedding_reindex_required`, пока все доступные chunks не получат выбранное generation. Переиндексация сначала полностью рассчитывает новое поколение и только затем атомарно публикует его; если source chunks изменились во время расчёта, публикация отклоняется с `rag_embedding_source_changed`, а прежнее generation остаётся целым. Сохранённые generations позволяют выполнить rollback возвратом прежней конфигурации без повторного чтения corpus.

`GET /rag/status` сообщает configured descriptor, `total_chunks`, `indexed_chunks`, `missing_chunks`, `pending_sources` и metadata доступных generations. Состояния имеют чёткий порядок: invalid provider configuration → `configuration_error`; новые/изменённые Markdown/Telegram sources → `ingest_required`; отсутствующее configured generation → `reindex_required`; совпадающий source/index → `ready`. Absolute paths и raw exception text наружу не передаются.

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

- Markdown/Telegram files из `rag_sources/profile-<id>/` являются явно profile-wide;
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

Session deletion удаляет принадлежащие ей derived documents/chunks/embeddings, но не profile-wide Markdown/Telegram sources и не соседние sessions. Profile deletion/reset удаляет profile source directory и все дочерние DB records. Git не является хранилищем пользовательского RAG.

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


## Telegram HTML через обычный RAG

В активном профиле откройте RAG → «Добавить файлы», выберите `messages.html` (и нужные `messages2.html` и т. д.), нажмите «Индексировать файлы» и включите RAG для чата. Обычные сообщения становятся отдельными фрагментами с датой, автором, ID и названием чата; служебные события не индексируются. Длинные сообщения разбиваются с повторением provenance в каждой части. Исходный экспорт не изменяется; загруженная копия хранится в профильном `rag_sources`, как Markdown.

Примеры последовательных запросов в одном чате:

1. «Найди сообщения, где обсуждали оркестрацию агентов».
2. «За какие даты эти сообщения? Укажи ID и авторов».
3. «Оставь за июль 2026» или «Только с 11.07.2026 по 15.07.2026».
4. «Уточни по ключевым словам: делегирование, задачи».

Поддержаны строгие фильтры ISO-даты, `DD.MM.YYYY`, диапазона из двух дат и русского месяца с годом. Текущая дата в уточнении имеет приоритет перед историей. Время остаётся временем экспорта; исходный timestamp с UTC offset сохраняется, если он есть. Даты без года не превращаются в строгий фильтр. Поиск остальных источников RAG продолжает работать по прежним правилам.

Для Telegram требуется `local_hash` и локальный endpoint chat-модели (`localhost`, `127.0.0.1`, `::1`). При внешнем endpoint или другом embedding-provider приложение возвращает явную ошибку, включая попытку переиндексации. Переключение на внешний chat-provider блокируется для профиля с проиндексированным Telegram. Это защита данного pipeline; существующие LAN-настройки и отсутствие шифрования SQLite остаются свойствами LocalGPT.

Хешевые embeddings не обеспечивают семантический поиск синонимов. Ответ использует текущие top_k и context budget, поэтому полный аудит каждого сообщения не гарантируется. Проверяйте приведённые ID/даты по исходному экспорту. Media-файлы не распознаются, ресурсы и ссылки из HTML не загружаются.

Для Markdown действуют прежние лимиты: 5 MiB на файл и 20 MiB на upload. Для Telegram HTML фиксированного ограничения байтов нет: upload читается потоком, разметка обработанных сообщений освобождается, проверенный файл публикуется атомарно. Через «Добавить файлы» можно выбрать больше 12 файлов за один раз: UI последовательно отправляет партии максимум по 12 файлов и примерно 20 MiB на HTTP-запрос. Один HTML больше 20 MiB отправляется отдельно; фиксированного ограничения размера HTML нет. Backend сохраняет лимит 12 файлов на отдельный запрос. Реальная ёмкость ограничена RAM/диском: нормализованный текст, chunks и векторы всё ещё требуют ресурсов при индексировании и поиске. Удаление файла из RAG очищает его индекс. Содержимое экспорта нельзя переносить в Git; тесты используют искусственные сообщения.


Уточнения поиска:

- `после`/`позже` и `раньше` задают исключительные границы; `с`/`не раньше` и `до`/`по`/`не позже` включают указанную дату.
- Явный `message123` или «ID: 123» ограничивает Telegram-результаты этим ID. Если указано имя HTML-файла, поиск ограничивается указанным источником; ID в разных чатах могут совпадать.
- `#BuildNotes`, `#build_notes` и «хэштег Build Notes» нормализуются для поиска одного тега. Это форматная нормализация, без новой семантической модели. В запросе с тегом формулировка «про <латинский технический термин>» дополнительно требует буквального наличия этого термина в сообщении (например, `#BuildNotes сообщения про alpha_tool`).
- Для гарантированного дословного текста запросите «Приведи полный текст message123 из messages.html дословно». Приложение извлекает исходное сообщение напрямую и сохраняет ответ в обычном чате, обходя перефразирование LLM и лимит top_k. Если требуется объяснить содержание или выделить факты, работает обычный RAG/LLM-ответ; его полнота зависит от контекстного бюджета.

Версия Telegram-парсера хранится в metadata; смена версии требует повторного ingest даже при неизменных размере/mtime файла. Индекс SQLite по chunk/model устраняет многократное сканирование embeddings при большом архиве.


## Ошибка добавления файла

При отказе загрузки окно RAG сохраняет причину и код; DevTools → Console показывает запись `[RAG upload]` с `code`/`reason` (и HTTP status для ошибки запроса). Console не получает содержимое файла, имя, FormData или raw payload. Ошибки отдельного файла могут прийти в успешном HTTP 200; они также выводятся в Console. Если не добавлено ни одного файла, интерфейс не предлагает индексировать.

Для HTML различаются отсутствующие история/заголовок/сообщения Telegram, незакрытый блок, повторяющиеся ID и неподходящая UTF-8 кодировка. Расширение `.html` само по себе не подтверждает формат Telegram Export. Для диагностики частного файла достаточно передать код ошибки; чтение файла облачным агентом не требуется.


Пакетная загрузка показывает общий прогресс по обработанным/добавленным файлам и ошибкам. Ошибка отдельного HTML не мешает добавлению остальных файлов. При ошибке HTTP/сети загрузка следующих партий останавливается; интерфейс показывает число файлов, для которых загрузка не подтверждена, и сохраняет результаты предыдущих партий. Автоматического повторения запроса после неопределённого сетевого сбоя нет. После завершения загрузки индексирование запускается обычной кнопкой.

`rag_upload_file_count_exceeded` относится к количеству файлов в одном HTTP-запросе и устраняется пакетами в обновлённом UI. `telegram_messages_not_found` — отдельный отказ конкретного HTML, в котором парсер не распознал завершённые сообщения; пакетная загрузка не отменяет эту проверку.


### Выдача найденных Telegram-сообщений

Явные запросы «найди/найти/найдите» и «покажи/список/ищи … сообщения» при наличии только Telegram evidence в выбранном контексте возвращают исходные фрагменты напрямую, без генерации пересказа моделью. Каждая карточка содержит источник, ID, исходную дату, автора и цитату; сокращение контекста отмечается. Это кандидаты из ограниченной RAG-выборки, а не подтверждение релевантности каждого результата или полноты поиска по всему корпусу. Остальные аналитические запросы продолжают использовать модель. Перечисленные через запятую темы разделяются на facets, чтобы оценивать их покрытие отдельно.

История сохраняет L4-envelope и original_role в provenance, но передаётся как user-data, чтобы не обучать модель формату ответа через assistant-role примеры. Служебные DATA_ENVELOPE-маркеры в сгенерированном ответе отклоняются с `model_output_transport_envelope`, включая маркер, разбитый между streaming chunks. В таком случае показывается ошибка вместо технической обёртки; содержимое обёртки не считается корректным ответом автоматически.

### Knowledge-only search

The composer `Поиск в базе` mode uses `POST /chat/knowledge-search`, independently of the existing RAG context toggle. It never calls chat preparation, model routing, generation or task workers. Search works without an installed chat model. Only local_hash is accepted; lexical_v1 avoids query embedding calls. Remote providers fail before retrieval, with no fallback to generation.

The endpoint validates profile/session ownership before retrieval and before persistence. Queries are limited to 4000 characters, top_k defaults to 8 (maximum 20), and evidence context is limited to 16000 characters including metadata. Results preserve source/chunk locators and available Telegram message ID, original timestamp and author. Truncation is explicit. These are lexical candidates, not an exhaustive semantic audit. Status distinguishes matches, no_matches and empty_index; retrieval errors leave history untouched.

Successful queries/results are saved in the original chat with model=knowledge_search. Images are rejected in this mode. Stop or a context/mode change aborts the browser request and rejects stale UI updates; cancellation does not undo a server write that already completed. Existing data is never deleted by mode changes.

Transport-format failures in normal generation are checked before continuation can reuse output. Invalid assistant history and summary turns are excluded from future context; records in the database are not rewritten. A single retry drops history wrappers while retaining current authorized evidence, system/profile instructions and original privacy controls. Streaming retries only before either answer text or reasoning has reached the client. A repeated format failure remains an explicit error, not an unpacked historical answer. Actual model compliance is not guaranteed.
