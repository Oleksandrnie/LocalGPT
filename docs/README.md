# Документация LocalGPT

## Что читать

| Задача | Основной документ |
| --- | --- |
| Установить и запустить LocalGPT | [Корневой README](../README.md) |
| Проверить dependency inventory и setup/bootstrap contract | [DEPENDENCIES.md](DEPENDENCIES.md) |
| Понять систему целиком | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Запустить или расширить проверки | [TESTING.md](TESTING.md) |
| Посмотреть значимые изменения | [CHANGELOG.md](CHANGELOG.md) |
| Спланировать незавершённую работу | [BACKLOG.md](BACKLOG.md) |
| Посмотреть постоянный план multimodal-аудита | [MULTIMODAL_AUDIT_PLAN.md](MULTIMODAL_AUDIT_PLAN.md) |
| Реализовать аудит prompt/RAG grounding и LLM-безопасности | [PROMPT_RAG_SECURITY_AUDIT_SPEC.md](PROMPT_RAG_SECURITY_AUDIT_SPEC.md) |
| Понять контракт и ограничения переноса моделей | [MODEL_TRANSFER_SPEC.md](MODEL_TRANSFER_SPEC.md) |
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
- Постоянный план и принятые результаты живут в `MULTIMODAL_AUDIT_PLAN.md`; active execution-state живёт в `temporary/<task-name>-progress.md` и удаляется после завершения задачи. `docs/progress/` предназначен только для постоянных исторических записей; `.gitkeep` сохраняет каталог.

При изменении кода обновляются только затронутые документы, а не вся документация проекта.
