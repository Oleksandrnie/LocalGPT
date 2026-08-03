# LocalGPT Agent Guide

`AGENTS.md` — единая точка входа для coding-агентов. Он задаёт workflow и ограничения, но не пересказывает архитектуру; технические факты берутся из [`docs/`](docs/README.md) и проверяются по коду.

## Назначение проекта

LocalGPT — локальный runtime для chat, ASR, TTS, OCR, RAG, plugins и private network access. FastAPI app собирается в `backend/server.py`, static UI живёт в `web_ui/`, модели и пользовательские данные остаются локальными.

## Обязательный порядок анализа

Перед изменениями:

1. Прочитать исходную задачу и выделить acceptance criteria.
2. Проверить ветку и `git status`; существующие изменения пользователя не перезаписывать.
3. Определить затронутые features, shared layers, runtime data и документы.
4. Прочитать обязательные документы из таблицы ниже.
5. Найти фактические entry points, imports, routes, schemas, storage и tests.
6. Сверить каждое существенное предположение с кодом/config; старые отчёты не являются доказательством.
7. Разделить работу на analysis, implementation, QA, documentation и cleanup.
8. Для существенной многоэтапной задачи создать progress-файл до изменения source files.

Если отсутствующий выбор способен заметно изменить результат или требует новой authority, остановиться и запросить решение. В остальных случаях сделать минимальное безопасное предположение и явно его зафиксировать.

## Обязательное чтение

| Тип задачи | Читать до реализации |
| --- | --- |
| Любая существенная задача | [`docs/README.md`](docs/README.md), [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), этот файл |
| Backend/API/shared storage | [`docs/knowledge/backend.md`](docs/knowledge/backend.md), [`docs/TESTING.md`](docs/TESTING.md) |
| Chat models, Ollama, ASR/TTS provider | [`docs/knowledge/providers.md`](docs/knowledge/providers.md), [`docs/TESTING.md`](docs/TESTING.md) |
| RAG или ASR context | [`docs/knowledge/rag.md`](docs/knowledge/rag.md), backend/providers по затронутому flow |
| Plugins | [`docs/knowledge/plugins.md`](docs/knowledge/plugins.md), [`docs/knowledge/networking.md`](docs/knowledge/networking.md) для address providers |
| LAN, Caddy, Tailscale, CORS | [`docs/knowledge/networking.md`](docs/knowledge/networking.md), [`docs/TESTING.md`](docs/TESTING.md) |
| Web UI, responsive, accessibility | [`docs/knowledge/ui.md`](docs/knowledge/ui.md), [`docs/TESTING.md`](docs/TESTING.md) |
| Планирование будущей работы | [`docs/BACKLOG.md`](docs/BACKLOG.md) |

Читайте дополнительные файлы только по затронутой подсистеме. Не загружайте всю документацию по привычке.

## Stage planning и progress tracking

Применяется к feature work, refactor, многофайловым bug fixes, большим спецификациям и задачам, которые могут продолжиться в другом чате.

Канонический путь:

```text
docs/progress/<task-name>-progress.md
```

Правила:

- `task-name` — lowercase kebab-case.
- `docs/progress/.gitkeep` сохраняется.
- `.gitignore` игнорирует остальные файлы в каталоге по умолчанию.
- Progress-файл явно добавляется через `git add -f` в первый stage commit и затем обновляется в каждом checkpoint.
- В нём фиксируются исходная цель, acceptance criteria, scope, риски, stages, decisions, changed files, validation, проблемы, следующий шаг и continuation prompt.
- Обновлять после значимой реализации, архитектурного решения, удаления, тестового прогона и перед checkpoint commit.
- Не удалять чужой или активный progress-файл. В частности, `docs/progress/asr-analysis-modes-progress.md` остаётся активным до отдельного завершения/подтверждения.
- После полного завершения своей задачи обновить только затронутую постоянную документацию и удалить свой progress-файл в финальном cleanup commit.

Для stage, который меняет tracked files:

1. реализовать только scope stage;
2. выполнить соответствующую validation;
3. обновить progress;
4. проверить staged diff;
5. создать один focused commit.

Research stage без tracked changes не требует пустого commit. Не переписывайте shared/pushed history и не используйте `git reset --hard`.

## Работа с кодом

## Ветки

- Не создавать отдельную ветку для задачи без явного запроса пользователя или прямого требования в этом `AGENTS.md`.
- Если отдельная ветка кажется подходящим решением, сначала предложить её пользователю с кратким обоснованием и дождаться явного подтверждения.
- Не считать обычную реализацию, исправление или исследование неявным разрешением на создание ветки.

- Предпочитать активные boundaries: feature logic в `backend/apps/<feature>/`, composition в `backend/server.py`.
- `app/` остаётся shared/transitional layer; не переносить код механически.
- `app/server.py` — compatibility import, не самостоятельный runtime.
- `compare-branch/` — read-only reference; runtime не должен импортировать его файлы.
- Новые routes держать тонкими: validation/serialization в router, логика в service/provider/repository.
- Сохранять profile isolation, explicit model loading, persisted task lifecycle и project-scoped storage.
- Plugin manifests — данные. Не исполнять код из `plugins/`; trusted behavior живёт в backend-owned handlers.
- Не хардкодить user-specific пути, transcript content, network addresses, domains или модели под один тестовый пример.
- Не добавлять silent fallback, который скрывает отсутствующую dependency, модель или invalid state.
- Не менять unrelated code и не исправлять найденный вне scope defect без отдельной authority; записать его в progress и при необходимости в `docs/BACKLOG.md`.

## Legacy и runtime files

- Не удалять/менять `app/prompts/system_base.md` как обычную документацию: он загружается `app/roles.py`.
- `LTrnsrb.*` — legacy aliases; новые инструкции используют `LocalGPT` / `start_localgpt*`.
- `compare-branch/` удаляется только после отдельного parity checklist.
- Component-owned docs, перечисленные в plugin manifest или описывающие ignored runtime folder, остаются рядом с компонентом.
- Не создавать внутри проекта папку `skills/`; Codex Skills находятся вне project docs.

## Тестирование

Validation должна быть пропорциональна риску. Общие команды и матрицы находятся в [`docs/TESTING.md`](docs/TESTING.md).

Безопасный baseline:

```bash
git diff --check
venv/bin/python -m compileall -q app backend tests
node --check web_ui/js/app.js
node tests/markdown_rendering.test.mjs
```

Выбирайте точечные unit tests по подсистеме; полный suite запускайте, когда это безопасно и полезно. Не запускайте live ASR, LLM/Ollama generation, full transcript pipeline или другую тяжёлую hardware-нагрузку без явного намерения и подходящей среды.

Для UI-изменений нужны затронутые desktop/mobile viewport, обе темы, keyboard/focus и relevant tool flows. Для networking — реальная LAN/tailnet проверка, если результат зависит от сети.

Не объявлять проверку пройденной, если команда не запускалась. Pre-existing failures отделять от новых regressions и фиксировать с точным test name/error.

## Документация: affected-documents approach

После изменения обновляются только документы, которые стали фактически неверными:

- обзор/запуск — `README.md`;
- cross-system architecture/data flow — `docs/ARCHITECTURE.md`;
- тестовые команды/критерии — `docs/TESTING.md`;
- subsystem contract — соответствующий `docs/knowledge/*.md`;
- завершённое значимое изменение — `docs/CHANGELOG.md`;
- незавершённая/отложенная проблема — `docs/BACKLOG.md`;
- agent workflow — `AGENTS.md`.

Не существует обязательного требования обновлять старый `TECHNICAL_README.md`; он не является частью текущей архитектуры. Не создавать дублирующую hub-копию component README.

## Запрещённые действия

- работать с существенной задачей прямо в protected/main branch, если задана рабочая ветка;
- стирать пользовательские изменения или использовать destructive Git/filesystem commands без явного запроса;
- механически переносить legacy docs/код без проверки;
- импортировать runtime из `compare-branch/`;
- исполнять arbitrary plugin code;
- открывать LocalGPT в public internet, включать Funnel/port forwarding по умолчанию;
- автоматически загружать/выбирать тяжёлую модель без явного действия пользователя;
- создавать project `skills/`;
- оставлять completed progress-файл;
- утверждать, что тесты или UI проверены, если они не запускались/не осматривались.

## Definition of Done

Задача завершена, когда:

- acceptance criteria выполнены;
- scope и архитектурные границы соблюдены;
- нет случайных/чужих изменений в diff;
- relevant static/unit/integration/manual checks пройдены либо точные внешние blockers зафиксированы;
- новые regressions устранены; pre-existing/out-of-scope issues отделены и записаны;
- команды, paths и ссылки проверены;
- затронутая постоянная документация обновлена без дублирования;
- temporary artifacts удалены;
- progress-файл текущей завершённой задачи удалён в финальном cleanup commit;
- `git status` чистый;
- итоговый отчёт перечисляет результат, validation, commits и deferred issues.
