# Changelog

Значимые завершённые изменения LocalGPT. Детали реализации остаются в Git history; временные progress-файлы сюда не копируются.

## Unreleased

### Added

- Интерактивный cross-platform setup (bootstrap) для macOS, Linux и Windows: native Terminal/PowerShell entry points, OS/package-manager detection, system/project dependency phases и final verification без загрузки моделей или пользовательских данных.
- Подтверждённый dependency inventory и закреплённые версии прямых Python packages для воспроизводимого первого запуска.
- Settings → System export/import complete Ollama, faster-whisper, whisper.cpp и Piper models через checksum-validated ZIP64 `.localgpt-models`, с выбором, прогрессом, подтверждением и conflict-safe publication.
- Settings → System показывает usage временных архивов model import и позволяет подтверждённо очистить только эти backend-owned `.localgpt-models` files.

### Changed

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
