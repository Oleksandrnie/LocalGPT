# LocalGPT Agent Guide

Этот файл — единая точка входа для coding-агентов, работающих с LocalGPT.

> Pending migration: полный workflow, таблица обязательного чтения, progress tracking, testing policy и Definition of Done будут перенесены на Stage 4.

## Перед началом работы

1. Прочитать задачу и определить затронутые подсистемы.
2. Открыть [индекс документации](docs/README.md).
3. Сверить существенные утверждения с кодом, а не со старыми отчётами.
4. Для многоэтапной задачи создать временный файл в `docs/progress/`.

## Границы

- Активный runtime собирается в `backend/server.py`; `app/server.py` — compatibility import.
- `compare-branch/` — read-only reference, не runtime-источник.
- `app/prompts/system_base.md` загружается приложением и не является обычным документом для реорганизации.
- Не создавать в проекте папку `skills/`.
- Не менять код или отдельные спецификации, не относящиеся к текущей задаче.

## Навигация

- [Архитектура](docs/ARCHITECTURE.md)
- [Тестирование](docs/TESTING.md)
- [Backlog](docs/BACKLOG.md)
- [Knowledge base](docs/README.md#база-знаний)
