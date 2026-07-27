# Документация LocalGPT

Короткий индекс постоянной документации проекта.

## Человеку

- [README проекта](../README.md) — возможности, требования и быстрый запуск.
- [Архитектура](ARCHITECTURE.md) — устройство runtime, границы и основные data flows.
- [Тестирование](TESTING.md) — стратегия, команды и критерии прохождения.
- [Changelog](CHANGELOG.md) — значимые изменения проекта.
- [Backlog](BACKLOG.md) — актуальные планы, технический долг и известные ограничения.

## Coding-агенту

1. Начать с [AGENTS.md](../AGENTS.md).
2. Прочитать этот индекс и документ нужной подсистемы.
3. Для многоэтапной работы использовать временный файл в [`progress/`](progress/).

## База знаний

- [Backend](knowledge/backend.md)
- [Providers](knowledge/providers.md)
- [Plugins](knowledge/plugins.md)
- [RAG](knowledge/rag.md)
- [Web UI](knowledge/ui.md)
- [Networking](knowledge/networking.md)

> Pending migration: содержимое целевых документов будет заполнено и проверено по коду на Stage 3.

## Ownership

- Обзор и запуск принадлежат корневому `README.md`.
- Системные границы и cross-subsystem flows принадлежат `ARCHITECTURE.md`.
- Подробности одной крупной подсистемы принадлежат соответствующему файлу в `knowledge/`.
- Команды и критерии проверок принадлежат `TESTING.md`.
- Завершённые изменения принадлежат `CHANGELOG.md`; незавершённая работа — `BACKLOG.md`.
- Временные task records хранятся только в `progress/` и удаляются после завершения своей задачи.
