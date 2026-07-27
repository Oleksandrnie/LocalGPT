# Документация LocalGPT

## Что читать

| Задача | Основной документ |
| --- | --- |
| Установить и запустить LocalGPT | [Корневой README](../README.md) |
| Понять систему целиком | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Запустить или расширить проверки | [TESTING.md](TESTING.md) |
| Посмотреть значимые изменения | [CHANGELOG.md](CHANGELOG.md) |
| Спланировать незавершённую работу | [BACKLOG.md](BACKLOG.md) |
| Работать coding-агентом | [AGENTS.md](../AGENTS.md) |

## База знаний

- [Backend](knowledge/backend.md) — структура, request lifecycle и границы `backend/apps/` / `app/`.
- [Providers](knowledge/providers.md) — Ollama, model routing, ASR и TTS provider contracts.
- [Plugins](knowledge/plugins.md) — Registry v0, manifests, trusted handlers и безопасность.
- [RAG](knowledge/rag.md) — ingestion, indexing, retrieval, storage и ASR context.
- [Web UI](knowledge/ui.md) — активный frontend, компоненты, responsive и accessibility.
- [Networking](knowledge/networking.md) — local, LAN, Caddy, Tailscale, host/port/CORS.

## Ownership

- Корневой `README.md` отвечает только за обзор, требования и запуск.
- `ARCHITECTURE.md` хранит cross-subsystem устройство и data flows.
- Файлы `knowledge/*.md` содержат подробности одной крупной подсистемы.
- `TESTING.md` — единственный общий источник тестовых команд и критериев.
- `CHANGELOG.md` хранит завершённые значимые изменения; `BACKLOG.md` — только незавершённую работу.
- Component-local README остаются рядом с конфигурацией, если их путь является частью runtime-контракта: `plugins/`, `plugins/tailscale/`, `rag_sources/`.
- Временные task records живут только в `docs/progress/` и удаляются после завершения своей задачи. `.gitkeep` сохраняет каталог.

При изменении кода обновляются только затронутые документы, а не вся документация проекта.
