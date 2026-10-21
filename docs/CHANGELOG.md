# Changelog

Значимые завершённые изменения LocalGPT. Детали реализации остаются в Git history; временные progress-файлы сюда не копируются.

## Unreleased

### Added

- Removed the unused Tailscale plugin, manual Serve integration and optional setup prompt; the explicit LAN/Caddy path remains available.

- Ollama per-model reasoning controls are discovered from `/api/show` and exposed in Settings and quick selectors; named levels are persisted and sent exactly, boolean-only models retain ON/OFF, and missing/unsupported metadata no longer relies on model-name heuristics. Direct Hugging Face inference remains out of scope.
- Installed non-catalog Ollama chat models now appear in the normal model selectors after inventory refresh; utility/Vision catalog entries and embedding-only models stay out of this chat list. The installer example now uses generic `model:tag` syntax.
- Added deterministic cross-domain Ollama evidence-use evaluation for installed chat models and sampled runner RSS, system memory pressure, swap deltas, unload and thermal-warning signals; post-answer RAG trace now follows the actual included evidence manifest even when heuristic facet status says `not_found`.
- Settings → Chat/LLM now provides a guarded Ollama model installer: raw model refs or a restricted `ollama pull` snippet, inline progress and cancellation, with independent backend validation and no automatic model selection or command execution.
- Code-enforced prompt/RAG/runtime security controls: metadata-only diagnostics/logging, task ownership, request/prompt/upload budgets, generation concurrency/timeout cleanup и bounded SSE reconnects.
- `ADMIN_TOKEN` authorization для runtime/database/storage/debug operations; Web UI передаёт token header-ом и хранит только в browser session.
- Domain-neutral `hybrid_v2` RAG retrieval с независимыми lexical/semantic pools, reciprocal-rank fusion, conservative semantic facet grounding, source diversity и provenance/status diagnostics; `lexical_v1` отключает semantic query для rollback, а `local-hash-v1` не выдаётся за semantic evidence.
- Cross-domain RAG eval теперь измеряет `ndcg_at_k` и идеальный начальный блок релевантных источников. Текущая semantic fixture насыщает этот ranking gate, поэтому optional reranker не добавлен без доказуемого качества и лишней локальной model/dependency нагрузки.
- Versioned local RAG embedding provider для Ollama `embeddinggemma`: provider/model/version/dimensions metadata, fail-closed vector validation, explicit atomic reindex и сохранение предыдущего generation для rollback без скрытого hashing fallback.
- RAG panel и API теперь показывают безопасный lifecycle configured embedding generation (`ready`, ingest/reindex required, configuration/operation failure), запускают только подтверждённую единственную background-переиндексацию с profile-owned progress и атомарно отклоняют публикацию при изменившихся sources.
- Контролируемая live-проверка `embeddinggemma` подтвердила полный semantic reindex и одинаковый retrieval snapshot для последовательных 3B/7B/4B ответов без одновременной model residency; различия полноты малых моделей зафиксированы отдельно от retrieval и перенесены в backlog как domain-independent улучшение.
- Chat reasoning теперь отделён от финального ответа в normal/SSE lifecycle, появляется в terminal modal live после первого chunk и остаётся persisted после completion/cancel/error; Thinking имеет рабочие ON/OFF controls и отдельные persisted output/thinking budgets с явно обозначенной per-call Ollama compatibility policy.
- User messages получили то же действие `Скопировать`, что и assistant messages: raw multiline/Markdown content передаётся в clipboard без изменения, а Chat → RAG остаётся отдельным действием.
- Любое user message и completed assistant message можно явно отредактировать и добавить в profile-scoped RAG; role/source metadata сохраняется, reasoning и binary исключены, source удаляется независимо.
- Settings → System can save Caddy's public LAN root certificate to the current computer for manual iPhone/Android transfer; the guarded no-store endpoint never serves a private key and is unavailable without live LAN HTTPS.
- Интерактивный cross-platform setup (bootstrap) для macOS, Linux и Windows: native Terminal/PowerShell entry points, OS/package-manager detection, system/project dependency phases и final verification без загрузки моделей или пользовательских данных.
- Подтверждённый dependency inventory и закреплённые версии прямых Python packages для воспроизводимого первого запуска.
- Settings → System export/import complete Ollama, faster-whisper, whisper.cpp и Piper models через checksum-validated ZIP64 `.localgpt-models`, с выбором, прогрессом, подтверждением и conflict-safe publication.
- Settings → System показывает usage временных архивов model import и позволяет подтверждённо очистить только эти backend-owned `.localgpt-models` files.
- Technical/security readiness report with architecture, P0–P3 risks, owner release gates and GitHub About/topics/release copy prepared without publishing or changing repository visibility.
- GitHub Actions quality workflow with pinned Actions, least-privilege permissions, deterministic Python/Node checks, incremental Ruff/Bandit, dependency audit and working-tree secret scan.

### Changed

- Обычный LocalGPT launcher стал local-only: macOS Caddy LAN-доступ запускается отдельной явной командой; добавлена отдельная команда остановки. ASR/OCR/criteria uploads и model-transfer ZIP processing получили bounded limits и cleanup. `python-multipart` обновлён до 0.0.31, Pillow до 13.0.0; минимальная версия Python согласована на 3.11+.
- Исправлена изоляция SQLite/ASR fixtures в полном Python suite, чтобы тесты не наследовали временный путь базы или ответы выключенных pipeline stages.

- Settings → Chat/LLM model library now separates installed models from available downloads and keeps update/delete/details actions in a per-model disclosure, with one clear primary action per row.
- Chat model `Thinking tokens` now defaults to 4096 with a 2048 minimum; old lower overrides are normalized in the effective UI/runtime settings while `Output tokens` remains independent.
- Post-answer RAG diagnostics now trace only evidence spans actually included in the prompt, even when the separate heuristic facet-status classifier says `not_found`.
- Chat/direct Vision и явный RAG-vision flow автоматически продолжают только подтверждённый provider length-stop с final content: до четырёх дополнительных проходов с прежним per-call budget, исходными instructions/evidence и exact overlap removal. Склеенный ответ проходит cross-pass privacy guard; cap exhaustion остаётся incomplete/failed и исключается из completed memory/history.
- Vision получил отдельный профильный output-token limit с default/reset 1024 и рекомендацией не снижать его; legacy `0` разрешается в 1024, а явные 128–8192 сохраняются без изменения обычного text budget. Provider `done_reason`/`eval_count` сохраняются, а ответ, оборванный лимитом, завершается явной ошибкой вместо ложного `completed`.
- Асинхронные ASR tasks используют один активный child-process и process-local FIFO с nonterminal `queued`; отмена queued-задачи очищает input без запуска worker, а active cancellation удерживает слот до подтверждённой смерти child.
- Model export/import теперь валидирует соответствие каждого payload file своей provider family, покрыт переносом между разными configured roots и сообщает, какие runtime нужно локально подготовить на новом устройстве; Ollama chat/Vision/embedding tags используют общий manifest/blob path.
- macOS whisper.cpp setup теперь сбрасывает stale CMake cache после перемещения checkout, собирает binary с relocatable `@loader_path`, создаёт относительную ссылку на `whisper-cli` и автоматически чинит старую ссылку.
- RAG completion теперь сообщает source/chunk answer trace по structured manifest фактически переданных evidence spans отдельно от retrieval `not_found`; служебные rules/filename/query и omitted chunks исключены из совпадений и IDs. Cross-domain regressions доказывают передачу evidence в фактический completion prompt, follow-up continuity и profile instruction presence без corpus-specific правил.
- Automatic chat summaries получили content-addressed completed-turn snapshot identity с `mem_turns`/compression budget, whole-turn truncation metadata и source-aware выбор актуального snapshot, поэтому edits/settings changes не переиспользуют stale summary и prompt не теряет его за более новыми memory rows.
- Short history и автоматическая summary memory теперь делят единый ordered набор завершённых `user + assistant` turns: failed/cancelled/active/partial и orphan rows не попадают в summary и не сдвигают retained-history boundary.
- Chat context теперь изолирован по `profile_id + session_id`: short history считает завершённые пары (default 6, `0` отключает), derived Chat/Vision/ASR RAG не переносится между чатами, а messages/criteria/transcripts/reasoning/attachments/tasks требуют matching session scope.
- Model output privacy больше не зависит только от prompt obedience: backend блокирует literal disclosure защищённых L1/L2/private-session значений до normal/streaming/vision delivery; отдельный metadata-only live harness проверен на трёх локальных Qwen-моделях.
- Public health/version, model inventory, TTS health и RAG status больше не раскрывают absolute storage paths/runtime hosts, а routed provider 5xx используют stable public errors; operational actions и chat task URLs получили явные authorization/ownership contracts.
- RAG sources and chat output now use one verified currency contract: `119 600 ₽`, `$500` and `€300`; commercial templates no longer use `руб.`, and malformed `⽇` after a numeric amount is normalized to `₽`.
- Hybrid Qwen Thinking OFF сохраняет structural reasoning boundary и больше не показывает/сохраняет chain-of-thought как ответ; token-limit completions fail closed. RAG follow-up удерживает последнюю тему через domain-neutral query composition/retrieval без специального CMS/platform bonus, а mobile message/session actions доведены до 44 px.
- Ordinary macOS startup now automatically provisions the private Caddy LAN HTTPS proxy while keeping the backend on localhost; the LaunchAgent runs from its runtime directory to avoid the reproduced no-listener startup hang, and missing Caddy falls back to an explicitly reported localhost launch.
- Generated LAN Caddy config теперь bind-ится только к текущему private IP, не создаёт wildcard HTTP redirect listener и принудительно перезапускает Caddy при изменении IP/actual backend upstream; diagnostic startup поддерживает `LOCALGPT_NO_BROWSER=1`.
- RAG принимает и индексирует только Markdown: автоматические JSON-дубли и их искусственный приоритет удалены, а reindex очищает старые JSON-записи из SQLite без удаления файлов пользователя.
- Диктовка в чате теперь проверяет готовность выбранной ASR-модели и whisper.cpp runtime до записи, открывая ASR-библиотеку с действием «Дособрать» вместо поздней ошибки транскрибации.
- Все cross-platform setup entry points собраны в `setup/`, их пути сделаны независимыми от текущего каталога; документация теперь явно различает штатный `venv/`, ручной `.venv/` и канонический `app/requirements.txt`.
- Setup `.command` корректно завершает успешную установку, а platform start launchers предпочитают подготовленный `venv` и не запускают LocalGPT через несовместимый системный Python.
- macOS setup теперь собирает и проверяет штатный `whisper.cpp` CLI без загрузки GGML-модели или CoreML encoder, поэтому default ASR backend готов после bootstrap.
- Chat-диктовка берёт язык активного ASR-профиля, предупреждает о записи короче 700 мс, а whisper.cpp runtime использует Silero VAD и decoder safeguards против hallucinations на тишине.
- Отдельная Vision-модель больше не наследует Thinking toggle text response model; `qwen3` с Thinking ON может использовать `qwen2.5vl` для image context без Ollama 400/последующего 502.
- Двухмодельный Vision route изолирует image analysis от profile/RAG/history, сохраняет OCR/visual evidence в исходном user turn и выгружает анализатор перед запуском chat response model; нерелевантный RAG больше не должен подменять текст скриншота.
- Финальный image-turn больше не зависит от списка команд: без явного RAG текущую команду сразу выполняет Vision-модель, поэтому корректно прочитанный скриншот не может быть испорчен вторым text-only проходом. Двухмодельное объединение используется только по явному запросу к RAG/базе знаний/документам; сохранённое сообщение указывает фактическую модель ответа.
- Пустой или тихий ASR input отклоняется по PCM-сигналу до Whisper, а короткие subtitle-credit hallucinations не сохраняются как транскрипт; UI получает сообщение `Речь в аудиофайле не обнаружена`.
- Прямой `python3 run_localgpt.py` снова работает с системным Python ниже 3.10: bootstrap автоматически продолжает через совместимый проектный `venv`, не изменяя системную установку.
- Выбор моделей для экспорта перенесён из развёрнутого списка Settings → System в отдельную responsive-модалку с select-all, счётчиком и явным подтверждением.
- Загрузка Ollama-моделей использует потоковый native `/api/pull`; CLI fallback больше не передаёт неподдерживаемый `ollama pull --json` и логирует фактический CLI/runtime transport при ошибках.
- Документация сведена к корневому `README.md`, `AGENTS.md`, постоянному набору `docs/` и component-owned README.
- Архитектура, тестирование и knowledge base разделены по зонам ответственности.
- Канонический путь временного tracking изменён на `docs/progress/<task-name>-progress.md`.

### Removed

- Дублирующие hub-копии README, technical, cleanup, map, backlog, UI, RAG, plugin и networking документов.
- Копия runtime prompt из документации; канонический файл остаётся в `app/prompts/system_base.md`.

## 2026-07-27

### Added

- Кнопка перехода к последнему сообщению с сохранением streaming auto-scroll поведения.
- Multimodal chat для PNG/JPEG/WebP: picker/paste/drop, локальные originals/thumbnails, persisted attachment/task lifecycle и direct Ollama vision route.
- Отдельный Settings tab `Vision` с библиотекой Qwen2.5-VL/Gemma 3, runtime-confirmed capabilities, profile limits, OCR assist и cache cleanup.
- Явный редактируемый Vision → RAG export производного текста без image binary.
- Настройка `Vision context, токены` в profile-owned Vision tab; значение передаётся в native Ollama `options.num_ctx` и устраняет зависимость от default 4096.

### Changed

- Завершён responsive mobile pass для chat composer, settings и ASR/TTS/OCR tools.
- Проверен ASR context lifecycle: сохранение как `asr_context`, RAG retrieval, включение в chat prompt и связанное удаление.
- Пользовательский live smoke multimodal chat принят: Qwen2.5-VL image flow и настройка Vision context работают штатно.

## 2026-05

### Added

- Persistent assistant-message lifecycle и SSE streaming для chat tasks.
- Plugin Registry v0 и trusted Tailscale handler.
- Model installation states, учитывающие configured store, active runtime и partial blobs.

### Changed

- LAN runtime синхронизирован с `.env`, а default CORS ограничен private/local origins.
- Chat, ASR, TTS, OCR и RAG развиваются как mini-app зоны под `backend/apps/`.

## 2026-04

### Added

- Profile-scoped RAG, ASR pipeline, summary memory и model-less startup.
- Voice Studio, OCR v1, light theme и обновлённый static Web UI.
- Database cleanup/reset для profile-owned данных без удаления локальных моделей.

### Deprecated

- `LTrnsrb.*` naming оставлен только как compatibility alias; основной launcher naming — `LocalGPT`.
