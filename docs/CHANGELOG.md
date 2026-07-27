# Changelog

Значимые завершённые изменения LocalGPT. Детали реализации остаются в Git history; временные progress-файлы сюда не копируются.

## Unreleased

### Changed

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
