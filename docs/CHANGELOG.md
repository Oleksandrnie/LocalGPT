# Changelog

Значимые завершённые изменения LocalGPT. Детали реализации остаются в Git history; временные progress-файлы сюда не копируются.

## Unreleased

### Added

- Code-enforced prompt/RAG/runtime security controls: metadata-only diagnostics/logging, task ownership, request/prompt/upload budgets, generation concurrency/timeout cleanup и bounded SSE reconnects.
- `ADMIN_TOKEN` authorization для runtime/database/storage/debug operations; Web UI передаёт token header-ом и хранит только в browser session.
- Offline `hybrid_v1` RAG retrieval с facet coverage, source diversity, duplicate suppression и provenance/status diagnostics; trust-aware L1/L2/L4 prompt composition отделяет policy/persona от untrusted evidence.
- Chat reasoning теперь отделён от финального ответа в normal/SSE lifecycle, появляется в terminal modal live после первого chunk и остаётся persisted после completion/cancel/error; Thinking имеет рабочие ON/OFF controls и отдельные persisted output/thinking budgets с честной one-pass Ollama policy.
- User messages получили то же действие `Скопировать`, что и assistant messages: raw multiline/Markdown content передаётся в clipboard без изменения, а Chat → RAG остаётся отдельным действием.
- Любое user message и completed assistant message можно явно отредактировать и добавить в profile-scoped RAG; role/source metadata сохраняется, reasoning и binary исключены, source удаляется независимо.
- Settings → System can save Caddy's public LAN root certificate to the current computer for manual iPhone/Android transfer; the guarded no-store endpoint never serves a private key and is unavailable without live LAN HTTPS.
- Интерактивный cross-platform setup (bootstrap) для macOS, Linux и Windows: native Terminal/PowerShell entry points, OS/package-manager detection, system/project dependency phases и final verification без загрузки моделей или пользовательских данных.
- Подтверждённый dependency inventory и закреплённые версии прямых Python packages для воспроизводимого первого запуска.
- Settings → System export/import complete Ollama, faster-whisper, whisper.cpp и Piper models через checksum-validated ZIP64 `.localgpt-models`, с выбором, прогрессом, подтверждением и conflict-safe publication.
- Settings → System показывает usage временных архивов model import и позволяет подтверждённо очистить только эти backend-owned `.localgpt-models` files.

### Changed

- Public health/version, model inventory, TTS health и RAG status больше не раскрывают absolute storage paths/runtime hosts, а routed provider 5xx используют stable public errors; operational actions и chat task URLs получили явные authorization/ownership contracts.
- RAG sources and chat output now use one verified currency contract: `119 600 ₽`, `$500` and `€300`; commercial templates no longer use `руб.`, and malformed `⽇` after a numeric amount is normalized to `₽`.
- Ordinary macOS startup now automatically provisions the private Caddy LAN HTTPS proxy while keeping the backend on localhost; the LaunchAgent runs from its runtime directory to avoid the reproduced no-listener startup hang, and missing Caddy falls back to an explicitly reported localhost launch.
- RAG принимает и индексирует только Markdown: автоматические JSON-дубли и их искусственный приоритет удалены, а reindex очищает старые JSON-записи из SQLite без удаления файлов пользователя.
- Диктовка в чате теперь проверяет готовность выбранной ASR-модели и whisper.cpp runtime до записи, открывая ASR-библиотеку с действием «Дособрать» вместо поздней ошибки транскрибации.
- Все cross-platform setup entry points собраны в `setup/`, их пути сделаны независимыми от текущего каталога; документация теперь явно различает штатный `venv/`, ручной `.venv/` и канонический `app/requirements.txt`.
- Setup `.command` корректно завершает успешную установку, а platform start launchers предпочитают подготовленный `venv` и не запускают LocalGPT через несовместимый системный Python.
- macOS setup теперь собирает и проверяет штатный `whisper.cpp` CLI без загрузки GGML-модели или CoreML encoder, поэтому default ASR backend готов после bootstrap.
- Chat-диктовка берёт язык активного ASR-профиля, предупреждает о записи короче 700 мс, а whisper.cpp runtime использует Silero VAD и decoder safeguards против hallucinations на тишине.
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
