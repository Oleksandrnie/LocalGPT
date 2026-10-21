# Документация LocalGPT

## Что читать

| Задача | Основной документ |
| --- | --- |
| Установить и запустить LocalGPT | [Корневой README](../README.md) |
| Проверить dependency inventory и setup/bootstrap contract | [DEPENDENCIES.md](DEPENDENCIES.md) |
| Понять систему целиком | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Запустить или расширить проверки | [TESTING.md](TESTING.md) |
| Проверить лицензию проекта | [GNU GPL-3.0-or-later](../LICENSE) |

## База знаний

- [Backend](knowledge/backend.md) — структура, request lifecycle и границы `backend/apps/` / `app/`.
- [Providers](knowledge/providers.md) — Ollama, model routing, ASR и TTS provider contracts.
- [Plugins](knowledge/plugins.md) — Registry v0, manifests, trusted handlers и безопасность.
- [RAG](knowledge/rag.md) — ingestion, indexing, retrieval, storage и ASR context.
- [Web UI](knowledge/ui.md) — активный frontend, компоненты, responsive и accessibility.
- [Networking](knowledge/networking.md) — local, direct LAN, host/port/CORS.

Архитектура, тесты и subsystem contracts описаны в соответствующих документах выше и в `knowledge/`. Модели и пользовательские данные не входят в исходный snapshot.
