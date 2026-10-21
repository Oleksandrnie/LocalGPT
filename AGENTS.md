# LocalGPT Agent Guide

`AGENTS.md` — обязательная карта и workflow-контракт для coding-агентов. Технические факты берутся из [`docs/`](docs/README.md) и проверяются по коду; этот файл не дублирует архитектурную документацию.

LocalGPT — локальный runtime для chat, ASR, TTS, OCR, RAG, plugins и private network access. FastAPI app собирается в `backend/server.py`, static UI живёт в `web_ui/`, модели и пользовательские данные остаются локальными.

## Authority, conversation и execution

Model routing применяется только к execution-задачам, которые изменяют состояние проекта или отдельно требуют review/audit. Вопросы, объяснения, brainstorming, планирование и обсуждение кода выполняет текущая выбранная пользователем модель без обязательного переключения или subagents: `conversation model != execution model`.

Приоритет выбора execution-модели:

1. Явная инструкция пользователя для текущей задачи.
2. Task-specific правила этого файла.
3. Общий routing ниже.
4. Модель текущего чата.

Пользователь может выбрать или запретить модель, effort, delegation, review или escalation. Такой override отменяет только model routing, но не Git, testing, validation, architecture, security, documentation, scope boundaries или Definition of Done.

## Model routing и subagents

`Bounded task` — задача с заранее понятными scope, ожидаемым результатом, architectural boundaries, acceptance criteria и validation. `Fine-grained edit` — локализованное изменение с понятным результатом. Luna исполняет определённую работу; Sol самостоятельно определяет правильное инженерное решение.

Для текущей мультимодальной работы пользователь задал отдельный routing: GPT-6 Luna с effort `Max` используется для рассуждений и синтеза результатов проверок; GPT-6.1 Sol с effort `Medium` — для архитектуры, технического дизайна и реализации, включая backend, lifecycle и persistence. Это заменяет прежние назначения для этих категорий. Routing зафиксирован здесь, в `AGENTS.md`; progress-файлы и subsystem-документы его не дублируют.

| Task | Default model | Effort |
| --- | --- | --- |
| Рассуждения, синтез evidence и анализ проверок в текущей мультимодальной работе | GPT-6 Luna | Max |
| Архитектура, технический дизайн и execution текущей мультимодальной работы | GPT-6.1 Sol | Medium |
| Fine-grained edit, простой HTML/CSS/UI | GPT-6 Luna | Low |
| Coordinated UI/responsive, bounded work по существующим patterns | GPT-6 Luna | Medium |
| Bounded implementation с полностью ясным контрактом | GPT-6.1 Sol | Medium |
| Backend/API/database/business logic, integrations, complex debugging/refactor | GPT-6.1 Sol | Medium |
| Architecture-sensitive implementation, persistence/lifecycle, substantial engineering | GPT-6.1 Sol | Medium |
| Routine independent review | GPT-6 Sol | Medium |
| Substantial multi-file или regression-sensitive review | GPT-6 Sol | High |
| Unusually deep/high-risk audit | GPT-6 Sol | xHigh when justified |
| Major architecture/migration/data-loss/security uncertainty | GPT-6 Astra | task-dependent |

Правила routing:

- Оптимизировать стоимость корректно завершённой задачи, а не первого вызова. GPT-6 Luna не является automatic target для других задач, но в текущей мультимодальной работе применяется для рассуждений с effort `Max` по указанному выше override.
- Если среда поддерживает model-specific subagents, orchestrator делегирует по этому routing и передаёт только необходимый context, requirements, constraints, relevant docs и validation criteria.
- Эскалировать с GPT-6 Luna Max на GPT-6.1 Sol Medium, если scope перестал быть bounded, неизвестен root cause, нужна migration/architecture, появились cross-system dependencies, сложный persistence/lifecycle или повторные разнородные failures.
- Mixed task делить по естественным technical boundaries, если это полезнее передачи всей задачи самой сильной модели; маленькую тесно связанную работу искусственно не дробить.
- Количество subagents определять структурой и риском. Несколько агентов оправданы для независимых параллельных частей, subsystem boundaries, сравнения подходов, ускорения сложной multi-part задачи или явно одобренного second opinion; agent swarm без понятной пользы запрещён.
- GPT-6 Sol — независимый reviewer, а не обязательное продолжение implementation. Review запускается только по прямому запросу пользователя либо после предложения агента и явного approval; prompt должен быть нейтральным.
- GPT-6 Astra — только architectural/high-risk escalation, включая нерешённый значимый архитектурный вопрос после Sol review, и не обязательный final reviewer. Нужны прямой запрос пользователя либо обоснованное предложение и явный approval. GPT-6.1 Sol High может заменить Astra только после явного согласования с пользователем.
- Automated/static/integration/manual validation важнее AI review; reviewer — дополнительный слой.
- Для сложной execution-задачи orchestrator кратко сообщает выбранный routing и причину, не превращая это в отдельный отчёт.

Локальные runtime-модели продукта не являются coding-agent routing. Provider contracts описаны в [`docs/knowledge/providers.md`](docs/knowledge/providers.md), data flows — в [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), фактический catalog — в [`app/config.py`](app/config.py). Runtime-оркестрация LocalGPT (manager/programmer/tester/reviewer) проектируется после стабилизации Chat/RAG/memory и ASR и не ограничивает Codex subagents.

## Обязательный workflow

Перед изменениями:

1. Выделить scope и acceptance criteria; проверить branch и `git status`, не перезаписывая пользовательские изменения.
2. Определить затронутые features, shared layers, runtime data, документы и подходящий model routing.
3. Прочитать обязательные документы ниже и найти фактические entry points, imports, routes, schemas, storage и tests.
4. Проверить существенные предположения по коду/config; старые отчёты не являются доказательством.
5. Разделить substantial work на analysis, implementation, QA, documentation и cleanup; до source changes создать progress-файл.
6. Если отсутствующий выбор заметно меняет результат или требует новой authority — запросить решение; иначе явно зафиксировать минимальное безопасное предположение.

### Обязательное чтение

| Тип задачи | Читать до реализации |
| --- | --- |
| Любая существенная задача | [`docs/README.md`](docs/README.md), [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), этот файл |
| Backend/API/shared storage | [`docs/knowledge/backend.md`](docs/knowledge/backend.md), [`docs/TESTING.md`](docs/TESTING.md) |
| Chat models, Ollama, ASR/TTS provider | [`docs/knowledge/providers.md`](docs/knowledge/providers.md), [`docs/TESTING.md`](docs/TESTING.md) |
| RAG или ASR context | [`docs/knowledge/rag.md`](docs/knowledge/rag.md), затем backend/providers по flow |
| Plugins | [`docs/knowledge/plugins.md`](docs/knowledge/plugins.md), а для address providers — [`docs/knowledge/networking.md`](docs/knowledge/networking.md) |
| LAN, CORS | [`docs/knowledge/networking.md`](docs/knowledge/networking.md), [`docs/TESTING.md`](docs/TESTING.md) |
| Web UI, responsive, accessibility | [`docs/knowledge/ui.md`](docs/knowledge/ui.md), [`docs/TESTING.md`](docs/TESTING.md) |
| Планирование будущей работы | [`docs/BACKLOG.md`](docs/BACKLOG.md) |

Дополнительные документы читать только по затронутой подсистеме.

### Stages, progress и checkpoints

Для features, refactors, многофайловых bug fixes, больших спецификаций и задач с возможным handoff использовать один active progress-файл:

```text
temporary/<task-name>-progress.md
```

- `task-name` — lowercase kebab-case. `docs/progress/` содержит только постоянные исторические записи; `.gitkeep` сохраняется, остальные файлы там ignored.
- Progress фиксирует goal, acceptance criteria, scope, risks, stages, decisions, changed files, validation, issues, next step и continuation prompt. Обновлять его после значимых решений/изменений/проверок и перед checkpoint.
- Явно добавить progress через `git add -f` в первый stage commit и обновлять в каждом checkpoint. Не удалять чужой/активный progress; `docs/progress/asr-analysis-modes-progress.md` остаётся активным до отдельного завершения или подтверждения.
- Каждый stage с tracked changes: реализовать только stage scope, выполнить proportional validation, обновить progress, проверить staged diff и создать один focused commit. Research-only stage не требует пустого commit.
- После полного завершения обновить только затронутые постоянные документы и удалить свой progress-файл в cleanup commit. Не переписывать shared/pushed history и не использовать `git reset --hard`.

## Project boundaries и invariants

- Предпочитать feature logic в `backend/apps/<feature>/`, composition в `backend/server.py`; новые routes держать тонкими, а логику — в service/provider/repository.
- `app/` — shared/transitional layer; `app/server.py` — compatibility import, не самостоятельный runtime. Не переносить legacy code механически.
- Сохранять profile isolation, explicit model loading, persisted task lifecycle и project-scoped storage. Сложные persistence/lifecycle changes требуют GPT-6.1 Sol Medium и проверки отложенных последствий для данных.
- Plugin manifests — данные; arbitrary code из `plugins/` не исполнять, trusted behavior держать в backend-owned handlers.
- `compare-branch/` — read-only reference: runtime не импортирует его файлы, удаление возможно только после отдельного parity checklist.
- Не хардкодить user-specific paths, transcript content, network addresses, domains или модели под один пример; не добавлять silent fallback для missing dependency/model или invalid state.
- Не менять unrelated code и не исправлять out-of-scope defects без отдельной authority; зафиксировать их в progress и при необходимости в [`docs/BACKLOG.md`](docs/BACKLOG.md).

## Git и safety

- Не создавать/switch отдельную branch без явного запроса пользователя или прямого требования этого файла. Если branch полезна, сначала предложить её и дождаться approval.
- Не работать над substantial task прямо в protected/main branch, если уже задана рабочая branch.
- Не стирать пользовательские изменения, не использовать destructive Git/filesystem operations и не переписывать shared history без явного запроса.
- Не открывать LocalGPT в public internet и не включать Funnel/port forwarding по умолчанию.
- Не загружать и не выбирать тяжёлую модель автоматически без явного действия пользователя.

## Legacy и runtime files

- `app/prompts/system_base.md` загружается `app/roles.py`; не менять/удалять его как обычную документацию.
- `LTrnsrb.*` — historical launcher aliases retained under `compare-branch/`; new instructions use `LocalGPT` / `start_localgpt*`.
- Component-owned docs, указанные в plugin manifest или описывающие ignored runtime folder, остаются рядом с компонентом.
- Не создавать project `skills/`; Codex Skills находятся вне project docs.

## Validation

Выбирать проверки пропорционально риску по [`docs/TESTING.md`](docs/TESTING.md). Безопасный baseline:

```bash
git diff --check
venv/bin/python -m compileall -q app backend tests
node --check web_ui/js/app.js
node tests/markdown_rendering.test.mjs
```

- Запускать targeted unit/integration tests по subsystem; full suite — когда это безопасно и полезно.
- Не запускать live ASR, LLM/Ollama generation, full transcript pipeline или другую тяжёлую hardware-нагрузку без явного намерения и подходящей среды.
- UI changes проверять в affected desktop/mobile viewports, обеих themes, keyboard/focus и relevant tool flows; networking — в реальной LAN-среде, если результат зависит от сети.
- Не объявлять проверку пройденной, если она не запускалась/не осматривалась. Отделять pre-existing failures от новых regressions с точным test name/error.

## Documentation

Обновлять только документы, которые стали фактически неверными:

- overview/setup — `README.md`;
- cross-system architecture/data flow — `docs/ARCHITECTURE.md`;
- validation commands/criteria — `docs/TESTING.md`;
- subsystem contract — соответствующий `docs/knowledge/*.md`;
- completed significant change — `docs/CHANGELOG.md`;
- deferred actionable work — `docs/BACKLOG.md`;
- agent workflow — `AGENTS.md`.

`TECHNICAL_README.md` не является текущим architecture source. Не создавать дублирующую hub-копию component README и не переносить legacy docs/code механически.

## Definition of Done

- Acceptance criteria выполнены; scope, architectural boundaries и security constraints соблюдены.
- Нет случайных, чужих или unrelated changes; новые regressions устранены, pre-existing/out-of-scope issues отделены и записаны.
- Relevant static/unit/integration/manual checks пройдены либо точные blockers зафиксированы; команды, paths и ссылки проверены.
- Затронутая постоянная документация обновлена без дублирования; temporary artifacts и завершённый progress-файл удалены.
- `git status` чистый; итоговый отчёт перечисляет результат, validation, commits и deferred issues. Не утверждать, что commit/push/test/UI check выполнен, если это не проверено.
