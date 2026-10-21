# Тестирование LocalGPT

## Стратегия

Проверки идут от дешёвых к дорогим:

1. static checks;
2. unit tests с temporary data и mocks;
3. API/backend smoke;
4. manual UI regression;
5. live ASR/Ollama/TTS/OCR только когда задача действительно затрагивает runtime и пользователь готов к нагрузке.

Live workload не является частью обычного документационного или безопасного regression pass: он может загружать модели, CPU/GPU и нагревать Mac.

## Быстрые проверки

Из корня проекта:

```bash
git diff --check
venv/bin/python -m compileall -q app backend tests
node --check web_ui/js/app.js
node tests/markdown_rendering.test.mjs
```

Setup/bootstrap contract без запуска package installers:

```bash
venv/bin/python -m py_compile setup/setup_localgpt.py tests/test_setup_dependencies.py
venv/bin/python -m unittest tests.test_setup_dependencies -v
/bin/sh -n setup/setup_localgpt.sh
/bin/zsh -n setup/setup_localgpt.command
```

`setup/setup_localgpt.py --verify-only` только проверяет текущее окружение, но возвращает non-zero при отсутствующих обязательных runtime components.

Если `venv/` ещё не создан, сначала запустите LocalGPT или установите `app/requirements.txt` в отдельное окружение.

## Unit tests

Полный текущий Python suite:

```bash
venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

Если рабочий `.env` выбирает live Ollama embedding provider, deterministic retrieval fixtures нужно отделить от runtime-конфигурации явным test override, чтобы unit suite не загружал локальную embedding-модель и не подменял compatibility baseline:

```bash
RAG_EMBEDDING_PROVIDER=local_hash \
RAG_EMBEDDING_MODEL=local-hash-v1 \
RAG_EMBEDDING_VERSION=local-hash-v1 \
RAG_EMBEDDING_DIMENSIONS=256 \
venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

Точечные наборы:

| Подсистема | Команда |
| --- | --- |
| Chat routing, Ollama lifecycle, SSE и RAG integration | `venv/bin/python -m unittest tests.test_model_router -v` |
| Chat reasoning runtime/budgets и explicit Chat → RAG | `venv/bin/python -m unittest tests.test_model_router tests.test_chat_rag -v` |
| Bounded text/direct Vision/RAG-vision continuation, overlap, cap и cross-pass privacy | `venv/bin/python -m unittest tests.test_chat_continuation -v` |
| Prompt/RAG security, hybrid retrieval и grounding diagnostics | `venv/bin/python -m unittest tests.test_prompt_rag_security_audit tests.test_chat_rag tests.test_vision_rag -v` |
| Cross-domain RAG retrieval baseline, metadata-only | `venv/bin/python -m unittest tests.test_rag_retrieval_eval -v` |
| Retrieval-to-answer contour, follow-up/profile policy и summary snapshot quality | `venv/bin/python -m unittest tests.test_chat_rag_answer_quality tests.test_chat_memory_boundary -v` |
| Versioned RAG embedding provider, atomic/background reindex, status и rollback | `venv/bin/python -m unittest tests.test_rag_embeddings -v` |
| RAG reindex UI lifecycle contract | `node --test tests/rag_reindex_ui.test.mjs` |
| Live-model harness contract без загрузки модели | `venv/bin/python -m unittest tests.test_live_llm_security_harness -v` |
| Profile/session isolation, completed-turn history и summary-memory boundary | `venv/bin/python -m unittest tests.test_chat_memory_boundary tests.test_context_isolation tests.test_chat_attachments tests.test_chat_rag tests.test_vision_rag -v` |
| Runtime authorization, ownership, redaction, limits и cleanup | `venv/bin/python -m unittest tests.test_runtime_security -v` |
| Chat image storage, lifecycle, vision runtime/output budgets/truncation, settings и RAG export | `venv/bin/python -m unittest tests.test_chat_attachments tests.test_chat_vision_context tests.test_chat_vision_lifecycle tests.test_chat_vision_runtime tests.test_vision_settings tests.test_vision_rag -v` |
| ASR pipeline, memory и ASR context | `venv/bin/python -m unittest tests.test_pipeline_memory -v` |
| whisper.cpp backend | `venv/bin/python -m unittest tests.test_whisper_cpp_backend -v` |
| ASR task FIFO, startup failures и cancellation lifecycle | `venv/bin/python -m unittest tests.test_asr_tasks -v` |
| TTS routes | `venv/bin/python -m unittest tests.test_tts_routes -v` |
| Piper provider | `venv/bin/python -m unittest tests.test_piper_provider -v` |
| WAV post-processing | `venv/bin/python -m unittest tests.test_audio_postprocess_service -v` |
| OCR heuristics | `venv/bin/python -m unittest tests.test_ocr_service -v` |
| Plugin Registry и Tailscale handler | `venv/bin/python -m unittest tests.test_plugin_registry -v` |
| Caddy LAN certificate download | `venv/bin/python -m unittest tests.test_network_certificate -v` |
| Model installation state | `venv/bin/python -m unittest tests.test_model_install_state -v` |
| Ollama pull API/CLI compatibility | `venv/bin/python -m unittest tests.test_ollama_pull -v` |
| Ollama model-reference input validation | `venv/bin/python -m unittest tests.test_ollama_model_ref_validation -v` |
| Ollama installer parser, custom chat-model discovery and UI contract | `node --test tests/chat_model_catalog.test.mjs tests/ollama_install.test.mjs tests/ollama_install_ui.test.mjs` |
| Model export/import bundle | `venv/bin/python -m unittest tests.test_model_transfer_manifest tests.test_model_transfer_inventory tests.test_model_transfer_export tests.test_model_transfer_import -v` |

Tests используют `unittest`; отдельные cases создают temporary SQLite/files и patch внешние процессы. Перед live-запуском всё равно проверяйте конкретный test body на обращение к локальным моделям/CLI.

Installer tests are offline: they validate raw model refs/snippet parsing and the UI contract only. They do not call Ollama, pull a model, run `ollama run`, or alter selected-model/profile settings. The backend repeats the model-reference validation at the pull boundary; an actual download remains an explicit, confirmed user action.

### Controlled live-model security smoke

Запускается только явно, с уже установленной моделью и работающим project-scoped Ollama. Harness выполняет восемь synthetic категорий последовательно, два раза, с `temperature=0`, bounded output и без client corpus. JSON содержит только model/runtime metadata и классификацию: raw prompts, ответы и значения canary не сохраняются.

```bash
venv/bin/python tools/live_llm_security.py --model qwen2.5:7b-instruct --repeats 2 --max-tokens 160 --output /private/tmp/localgpt-live-security.json
```

На 16 GB Mac запускайте модели строго по одной. Exit `0` означает отсутствие итогового hard boundary breach; exit `2` — незаблокированную prompt-boundary/disclosure ошибку; exit `3` — runtime/harness error. `raw_model_disclosures` отражает слабость самой модели, а `backend_blocked_outputs` — fail-closed срабатывания до выдачи результата. Behavioral jailbreak фиксируется отдельно и не считается действием: harness не предоставляет model-output-to-action edge.

### Cross-domain RAG retrieval baseline

Offline eval использует только synthetic Markdown из нескольких несвязанных областей и временные SQLite/RAG directories. Он не читает пользовательский corpus, не загружает LLM/embedding model и сохраняет только агрегаты и case IDs: raw query/content в report отсутствуют.

```bash
venv/bin/python tools/rag_retrieval_eval.py --pretty --output /private/tmp/localgpt-rag-baseline.json
```

Основные метрики: `recall_at_k`, `mrr`, binary-relevance `ndcg_at_k`, `ideal_ranked_hit_rate`, `context_recall`, `grounded_hit_rate`, negative rejection и expected evidence-status accuracy. `ndcg_at_k=1` вместе с `ideal_ranked_hit_rate=1` означает, что все размеченные источники занимают первые `expected_source_count` позиций; это gate для решения о необходимости reranker, а не оценка полноты самой разметки. Raw hit без `supported`/`partial`/`conflict` diagnostics не считается grounded success. `resources` — локальное наблюдение конкретного запуска, не стабильный benchmark. Сравнивайте retrieval implementations на неизменном fixture manifest; не добавляйте туда client/company corpus или production-specific vocabulary.

## Backend smoke

Терминал 1:

```bash
venv/bin/python -m uvicorn backend.server:app --host 127.0.0.1 --port 8000
```

Терминал 2:

```bash
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8000/ui/gui_html.html
```

Smoke считается пройденным, если `/health` возвращает `status: ok`, UI отдаётся без 5xx, а запуск не создаёт неожиданных tracked files. Если порт занят, используйте свободный порт или штатный launcher.

## Проверки подсистем

### Chat и providers

- manual/auto model selection не загружает модель без явного действия;
- missing/partial/installed/active states не смешиваются;
- `stream=true` создаёт раздельные SSE `reasoning`/`delta`, а replay/reconnect не дублирует ни reasoning, ни final text;
- non-streaming сохраняет тот же assistant lifecycle;
- native reasoning отделён от final content в normal/streaming paths, инкрементально сохраняется, не входит в SSE `delta`/history; hybrid Qwen OFF сохраняет structural parser, использует output + thinking compatibility cap и скрывает reasoning; только явный length с final content запускает до четырёх продолжений с тем же per-call budget; cap/empty/reasoning-only exhaustion завершается ошибкой и очищает partial assistant row;
- Ollama `thinking.values/default` sanitization covers named levels, boolean-only controls, `[false]`, absent/malformed metadata and catalog/custom installed inventory; settings validate per-model choices, persist named values exactly, preserve legacy `auto/on/off`, and native sync/stream payloads send exact declared values without name-based guessing;
- deterministic continuation fixtures проверяют task stream/non-stream, direct Vision с теми же images, explicit RAG-vision без нового retrieval, exact overlap, единственный terminal SSE и privacy literal через границы passes;
- protected L1/L2/private-session literal блокируется до non-streaming выдачи/сохранения; streaming/vision guard не выпускает полное значение даже при разбиении между chunks; user attack marker не считается protected автоматически;
- `output_tokens`/`thinking_tokens` мигрируют и round-trip независимо; быстрый Thinking не сбрасывает их; settings, desktop/mobile header menus and quick model picker show only discovered per-model reasoning values, and trace visibility remains separate;
- thinking budget defaults to 4096 and rejects/clamps values below 2048 while preserving the separate output-token range and higher per-model overrides;
- RAG context попадает в prompt только активного профиля;
- RAG data остаётся L4 envelope; `hybrid_v2` покрывает multi-part facets через independent lexical/semantic pools и RRF без corpus-specific bonus, repeated/deictic recent turns сохраняют релевантную тему, а missing/conflicting evidence получает `not_found`/`conflict` diagnostics с provenance;
- sync/task answer diagnostics сохраняют facet retrieval status отдельно и оценивают trace только против structured manifest evidence spans, реально включённых в prompt: `not_found` без manifest — `evidence_not_found`, а manifest с lexical overlap / без него — `evidence_traceable` / `evidence_found_answer_not_traceable`; rules/filename/query, обрезанный хвост и полностью omitted chunk не считаются evidence, source/chunk IDs перечисляют только manifest entries, а последний status требует review и не считается semantic verdict;
- profile prompt, memory, criteria и language policy сохраняют порядок.
- short history использует default 6 и проверяется для `0/1/6/100`: один turn равен завершённой паре `user + assistant` только активной session; summary compression получает непересекающийся prefix тех же completed turns, режет input только между целыми turns, меняет snapshot identity после edit/`mem_turns`/`max_context_chars` и source-aware сохраняет текущий snapshot при более чем 100 новых summary rows; orphan/active/failed/cancelled/partial rows и текущий query не считаются и не сдвигают split;
- messages/criteria, transcript/pipeline, reasoning, attachment, task и derived-RAG endpoints отклоняют foreign profile/session тем же not-found contract, что unknown ID;
- max-valid request проходит, а oversized block/aggregate/assembled prompt возвращает bounded 4xx до generation;
- task status/events/cancel отклоняет foreign profile/session тем же contract, что unknown task; concurrency, timeout, cancel/error cleanup и SSE connection limit завершаются terminal state без partial artifacts;
- runtime/database/storage/debug без `ADMIN_TOKEN` не выполняют side effect, а public/log/debug/provider failures не содержат synthetic secret/path marker;
- PNG/JPEG/WebP upload проверяет profile ownership, count/byte/pixel/side limits и не сохраняет binary в message/RAG;
- direct image route доступен только при runtime-confirmed `vision`, а text-only model использует явный context route;
- Vision context size сохраняется в profile settings и уходит в native Ollama как `options.num_ctx` для direct/streaming inference;
- отдельная vision-модель в `vision_context` route не наследует Thinking toggle выбранной text response model;
- отдельный Vision analysis prompt не содержит profile/RAG/history, OCR и derived visual evidence остаются внутри текущего user turn, а image evidence имеет приоритет над нерелевантным RAG этого же профиля;
- любые image-команды без явного RAG выполняет сама Vision-модель в одном чистом current turn, без command-specific классификатора и второго text-only прохода; RAG retrieval не запускается и envelope не добавляется без явного запроса к RAG/базе знаний/документам;
- завершённый assistant message хранит фактическую модель генерации (`qwen2.5vl:*` для прямого image response), а не выбранную, но не вызванную text-only chat-модель;
- attachment lifecycle связан с persisted user message/task, refresh/cancel и cleanup не оставляют active record в неверном terminal state.

Static UI contract для attachment composer, Vision tab и explicit RAG export:

```bash
node tests/chat_attachments_ui.test.mjs
node tests/chat_reasoning_ui.test.mjs
```

System Settings model-transfer contract:

```bash
node tests/model_transfer_ui.test.mjs
```

System Settings LAN certificate controls:

```bash
node tests/lan_certificate_ui.test.mjs
```

### LAN/Caddy

Проверка launcher-контрактов не поднимает тяжёлые модели и не открывает браузер:

```bash
/bin/zsh -n tools/LTrnsrb.sh
venv/bin/python -m unittest tests.test_lan_launcher tests.test_network_certificate
```

Для реального LAN smoke запускайте launcher с `LOCALGPT_NO_BROWSER=1`, если автоматическое открытие окна не нужно. Проверяйте, что backend слушает только фактический `127.0.0.1:<runtime-port>`, а Caddy — только выбранный частный LAN IP и HTTPS-порт; listener на `0.0.0.0`, `*:80` или устаревший upstream недопустим.

Через HTTPS проверяются `/health`, UI и static assets, profile/model API, потоковый chat SSE, разрешённый и запрещённый CORS Origin, отказ privileged API без `ADMIN_TOKEN` и выдача только публичного root CA без private key. После изменения IP или runtime-порта launcher должен пересобрать конфигурацию и перезапустить Caddy.

Stage 7 LAN validation считается завершённой только после проверки со второго устройства в той же частной сети: UI/API открываются, SSE-ответ приходит, `/health` доступен, privileged endpoint без токена получает отказ, а клиент доверяет установленному публичному Caddy root CA. Не включайте Funnel, port forwarding или публичную привязку backend.

Model-transfer tests используют только temporary synthetic files. Relocation regression создаёт chat/Vision/embedding Ollama, faster-whisper, whisper.cpp и Piper fixtures в source roots, проверяет отсутствие absolute source paths в manifest и импортирует их в другой набор configured destination roots. Отдельно проверяются destination runtime requirements; платформенные executable не считаются частью bundle. Реальный export/import локальных моделей запускается отдельно явным действием пользователя.

Контролируемый live vision smoke запускается отдельно после явной установки модели. Используйте маленькое детерминированное изображение, `temperature=0`, ограниченный `max_tokens`, последовательный запуск и `keep_alive=0`; проверьте точный текст/формы, отсутствие CPU fallback, terminal task/attachment state, отсутствие binary/path в messages и пустой `ollama ps` после теста. Не загружайте 3B и 7B одновременно на 16 GB машине.

Если Ollama сообщает `request (...) exceeds the available context size (4096)`, откройте Settings → Vision → `Vision context, токены`, сохраните 8192 (для более длинной истории — 16384) и повторите запрос. Значение применяется к следующему vision task.

### ASR

- deterministic `test_asr_tasks` подменяет process/monitor без реального inference: один активный child, FIFO `queued`, queued cancel/input cleanup, удержание cancelling slot до смерти, идемпотентные monitor/poll, error/resultless exit, constructor/start/monitor failures и bulk-cancel dispatch barrier;
- быстрый voice-to-input и ASR Studio остаются разными UX flows;
- chat-диктовка использует language/prompt preset активного профиля; запись короче 700 мс не отправляется в ASR;
- `whisper.cpp` использует Silero VAD, PCM signal gate и short credit-artifact filter, чтобы тишина не превращалась в вымышленную транскрипцию; no-speech не создаёт transcript record и возвращает понятное `empty_transcription`;
- backend selection соответствует `WHISPER_BACKEND`;
- disabled stage не запускается ни одним analysis mode;
- `full` требует `asr_full_analysis_enabled`;
- ASR context индексируется, ищется и удаляется вместе со связанной записью.

Не запускать live transcription/full pipeline без осознанной проверки ресурсов.

### TTS

- health/voices/library endpoints работают без повреждения history;
- provider корректно обрабатывает missing runtime/model;
- generation пишет output и history;
- speed processing создаёт валидный WAV и не перезаписывает исходник неожиданно.

### OCR

- API принимает только поддерживаемые изображения;
- отсутствующий Tesseract возвращает понятную ошибку;
- language fallback и UI-noise cleanup не удаляют значимый текст.

### RAG

- profile isolation;
- validation только `.md` и отклонение legacy `.txt`/`.json`;
- force reindex очищает stale JSON records, не удаляя legacy files;
- chunk overlap, embedding metadata, `hybrid_v2` independent pools/RRF, `lexical_v1` rollback, `legacy` compatibility и diversified top-k search;
- versioned provider/model/dimensions не смешиваются; несовместимый Ollama response fail-closed, explicit reindex атомарно публикует новое generation и сохраняет прежнее для rollback;
- status различает `ready`/`ingest_required`/`reindex_required`/`configuration_error`, task polling требует owning profile, raw provider errors не возвращаются, а изменение source chunks во время reindex отменяет публикацию;
- context assembly соблюдает `max_chars` и содержит bounded facet/provenance diagnostics;
- generic follow-up выбирает evidence через ordinary lexical/semantic relevance без platform/company bonus, а query composer не дублирует turns и сохраняет последнюю тему для коротких/склонённых deictic forms;
- search соблюдает query/top-k limits; multi-file upload проверяет count/per-file/total bytes до publication и не оставляет artifacts при 413;
- file/context deletion очищает DB records.
- explicit user/completed-assistant export проверяет profile/session ownership, role metadata, отсутствие reasoning и независимое удаление; assistant-authored export не принимается как factual evidence;
- derived Chat/Vision/ASR retrieval доступен только исходной session, а profile-wide Markdown остаётся доступным всем sessions активного profile; session deletion очищает только её derived index;
- corpus audit metadata-only, preview-only и не изменяет source/index (`mutations_performed=0`).

### Plugins и networking

- malformed manifest остаётся видимым как invalid/untrusted;
- untrusted plugin нельзя effectively enable;
- docs path не выходит из plugin directory;
- Tailscale checks read-only и не запускают Serve/Funnel;
- core LAN/Tailscale addresses возвращаются backend-ом, а не hardcode-ятся UI.

## UI regression

`node --test tests/model_thinking_ui.test.mjs tests/chat_reasoning_ui.test.mjs tests/chat_model_catalog.test.mjs` checks named-level and boolean metadata, custom installed models, explicit/unknown unsupported states, settings/header synchronization, and unchanged token budgets. Full frontend checks use `node --test tests/*.test.mjs`.

Минимальная ручная матрица:

- desktop и mobile viewport;
- dark/light theme;
- sidebar, chat library, scroll-to-latest;
- profiles/sessions и Settings tabs;
- streaming и refresh/reconnect;
- ASR/TTS/OCR tool docks;
- RAG panel и context section: generation state, disabled/confirm reindex action, progress/failed state и refresh-resume на desktop/mobile в обеих темах;
- image picker/paste/drop, attachment preview/remove/history и Vision → RAG dialog;
- live reasoning icon/modal, close/reopen и cancel/error retention, два token budget поля, оба mobile Thinking controls и их cross-sync, user/assistant Copy и общий Chat → RAG dialog;
- mobile session actions и message `Добавить в RAG`/`Скопировать` имеют фактический tap target не меньше 44 px;
- Vision settings/library, runtime capability state и cache cleanup;
- Plugins и network-address menu;
- keyboard focus, aria states и reduced-motion-sensitive flows.

Активный UI — `web_ui/gui_html.html` + `web_ui/js/app.js`. Старый modular flow под `web_ui/js/main.js` не подключён HTML entry point и не должен считаться текущим runtime без отдельной миграции.

## Platform-specific

- macOS: `.command` launchers, Caddy certificate trust, whisper.cpp Metal/CoreML, microphone permissions;
- Windows: `start_localgpt.bat`, Python launcher resolution, filesystem paths;
- Linux: executable bit на shell scripts, `ffmpeg`, Tesseract и Ollama service.

## Setup/bootstrap acceptance на новом окружении

Эта проверка намеренно ручная: она устанавливает system packages и может запросить administrative privileges.

1. На чистом macOS/Linux/Windows environment запустить соответствующий `setup/setup_localgpt.*` entry point.
2. Проверить корректное определение ОС и package manager, понятные confirmation prompts и отсутствие речевых model downloads. На macOS убедиться, что `models/whisper_cpp/bin/whisper-cli` — исполняемая относительная ссылка на собранный binary, переживает перенос checkout и заменяет stale link при повторной подготовке; `models/whisper_cpp/ggml-silero-v6.2.0.bin` должен быть установлен для VAD.
3. Согласиться на core dependencies; optional Caddy/Tailscale/Node проверить отдельно по нужному режиму.
4. Убедиться, что final verification проходит и `venv/` содержит imports из `app/requirements.txt`.
   Отдельный `.venv/`, если он существовал до setup, должен остаться нетронутым и не считаться штатным runtime environment.
5. Повторить setup: установленные system tools должны быть пропущены, pip не должен ломать environment.
6. Запустить `start_localgpt*`, проверить `/health` и `/ui/gui_html.html` по Backend smoke выше.
7. Убедиться, что `.env`, models, RAG sources, profiles и public networking не создавались автоматически.

Результаты platform acceptance фиксируются в активном task progress до финального cleanup.

## Критерии прохождения

- команды завершаются с exit code 0;
- нет новых traceback, 5xx, зависших tasks или tracked runtime artifacts;
- тесты не используют реальные модели без явного намерения;
- изменения UI проверены в затронутых viewport/theme состояниях;
- документация и команды соответствуют текущему коду.

## Известные ограничения

- автоматизированного end-to-end browser suite в репозитории нет;
- live ASR/LLM/TTS/OCR зависит от установленных binaries, моделей и hardware;
- vision output зависит от модели; smoke должен проверять заранее известные признаки изображения, а не точную формулировку ответа;
- LAN/Tailscale требуют проверки в реальной сети;
- manual accessibility и mobile regression остаются обязательными для заметных UI-изменений.
