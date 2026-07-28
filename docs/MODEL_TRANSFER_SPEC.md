# ТЗ: безопасный перенос локальных моделей

## Статус и цель

Статус: MVP реализован; реальный перенос пользовательских моделей ещё не проходил user-controlled smoke.

Нужно дать пользователю LocalGPT простой способ перенести установленные модели между независимыми профилями macOS и Windows. Перенос выполняется из интерфейса LocalGPT как скачивание одного bundle-файла и последующий импорт этого файла; способ передачи между компьютерами выбирает пользователь.

Основной пользовательский сценарий:

1. В профиле-источнике пользователь открывает Settings → System, нажимает «Экспорт моделей» и выбирает установленные модели либо «Выбрать все».
2. LocalGPT создаёт один переносимый `.localgpt-models` файл, проверяет включённые файлы и отдаёт его браузеру как download.
3. В профиле-получателе пользователь нажимает соседнюю кнопку «Импорт моделей», выбирает bundle обычным file picker, видит предварительный план и подтверждает импорт.
4. LocalGPT проверяет пакет и место, устанавливает модели в configured model paths этого профиля и повторно проверяет их штатными discovery-процедурами.

## Важное ограничение

Архив не может уменьшить физически необходимое место: веса LLM, GGML и ONNX уже в основном сжаты. Экспорт занимает не меньше суммы уникальных выбранных файлов плюс небольшой служебный overhead. Дедупликация общих Ollama blobs уменьшает размер только тогда, когда несколько выбранных тегов используют один и тот же blob.

LocalGPT не определяет способ транспортировки, тип носителя или формат файловой системы. Bundle можно сохранить и передать любым доступным пользователю способом. Shared model drive, volume discovery и filesystem-format policy полностью исключены из scope.

## Scope

### Входит в MVP

- Экспорт и импорт полных, локально установленных артефактов следующих provider families:
  - Ollama chat/vision models;
  - faster-whisper model directories, найденных штатным ASR discovery;
  - whisper.cpp GGML/CoreML model assets;
  - Piper voice pairs (`.onnx` и соответствующий `.onnx.json`).
- Выбор конкретных моделей, preview объёма, дедупликация Ollama blobs, прогресс, отмена и понятный отчёт.
- Целостность файлов, безопасная публикация модели только после проверки и provider inventory refresh после import.
- Импорт в текущие configured paths из `app.config.MODEL_PATHS`; absolute paths профиля-источника, имена macOS/Windows account и Windows drive letters не переносятся.

### Не входит в MVP

- Загрузка всего bundle в память браузера или backend; download/upload должны использовать потоковый либо spooled disk I/O.
- SQLite, profiles, sessions, prompts, RAG sources, chat attachments, TTS history, logs, `.env`, API keys и пользовательские настройки.
- Partial downloads, Ollama runners, binary `whisper-cli`, Python virtualenv, arbitrary executable files и неизвестные caches.
- Автоматическое удаление исходной модели после экспорта или удаление уже установленной модели при конфликте.
- Перенос между архитектурами/ОС как обещание работоспособности: package переносит байты, но provider/runtime остаётся ответственностью целевого профиля.

## Фактические границы текущего runtime

| Family | Текущая canonical location | Что считается установленным |
| --- | --- | --- |
| Ollama | `models/ollama/` или configured `OLLAMA_MODELS_DIR` | manifest и все referenced blobs; один blob может быть общим у нескольких моделей |
| faster-whisper | `models/whisper/` / `WHISPER_MODELS_DIR` | директория модели, признанная `backend.apps.asr.downloads` |
| whisper.cpp | `models/whisper_cpp/` / `WHISPER_CPP_MODELS_DIR` | выбранный GGML model file и связанные CoreML assets, если они нужны этой модели |
| Piper | `models/tts/piper/` / `PIPER_MODELS_DIR` | `.onnx` вместе с `.onnx.json` |

Пути могут переопределяться `.env`. Экспортёр обязан брать их из запущенного `config.MODEL_PATHS`, а не предполагать `models/` в корне репозитория. Текущее состояние установки Ollama уже умеет различать `installed`, `partial` и отсутствующий blob; новый transfer service обязан использовать ту же семантику.

## Решение: LocalGPT Model Bundle v1

### Один несжатый ZIP64 bundle

MVP использует один ZIP64-контейнер с расширением `.localgpt-models`, например `LocalGPT-models-2026-07-27.localgpt-models`. Entries записываются в режиме `stored` без сжатия: веса уже сжаты, а ZIP64 поддерживает файлы больше 4 GiB.

Browser download и import upload не должны загружать весь bundle в память. Упрощённый MVP не обещает resume оборванной сетевой передачи одного archive-файла; пользователь повторяет download/upload.

### Структура пакета

```text
<name>.localgpt-models          # ZIP64, compression=stored
  manifest.json
  payload/
    ollama/
      manifests/<original relative path>
      blobs/sha256-...
    faster-whisper/<model id>/<relative path>
    whisper-cpp/<model id>/<relative path>
    piper/<voice id>/<relative path>
```

`manifest.json` — UTF-8 JSON, schema `localgpt-model-bundle`, version `1`. Он содержит только переносимые metadata: bundle ID, время создания, минимальную версию LocalGPT, producer platform (diagnostic only), выбранные model IDs, family, provider metadata, список payload files, их POSIX-relative path, byte size и SHA-256. Для Ollama он содержит model name/tag, относительный путь manifest и список digest каждого required blob. Никаких исходных absolute paths, drive letters, токенов, profile IDs, user names или содержимого БД в manifest нет. Manifest paths обязаны быть уникальны также при case-insensitive сравнении, чтобы package одинаково работал на default macOS и Windows filesystems.

Центральный каталог ZIP, `manifest.json`, допустимый entry set, размеры и SHA-256 должны быть корректны. Оборванный или недописанный archive не импортируется.

### Правила создания

1. Перед стартом service получает process-wide model-transfer lock. В это время pull, delete, prepare/update, preload и новый model export/import получают контролируемую ошибку `model_transfer_in_progress`.
2. Активные model tasks должны завершиться, быть отменены пользователем либо быть выгружены штатным runtime lifecycle. Экспорт не читает артефакты, пока соответствующая загрузка/обновление в progress.
3. UI показывает точный прогноз уникальных байтов и предупреждает, что browser download потребует соответствующее свободное место.
4. Service не принимает destination path и не обнаруживает volumes: место сохранения download выбирает браузер/ОС.
5. Каждый source path должен быть regular file внутри допустимого provider root. Симлинки, sockets, hidden temporary artifacts, `*-partial*` и неизвестные executable files отклоняются и включаются в отчёт как excluded.
6. Файлы потоково записываются в ZIP64; для каждого вычисляются size и SHA-256. Временный archive backend удаляется после завершения download task либо при cleanup.
7. Для Ollama export сначала строит dependency graph из manifest-ов и включает каждый digest один раз. Экспорт невозможен, если выбранный model manifest не парсится или хотя бы один required blob отсутствует.
8. Только полностью закрытый и проверенный ZIP публикуется как downloadable result. Исходные модели остаются неизменными.

## Импорт

### Inspect до подтверждения

`inspect` не пишет в model storage. Он:

- принимает выбранный пользователем `.localgpt-models` файл через upload;
- проверяет ZIP64 structure, schema version, syntax manifest, allowed family/path set и уникальность путей;
- сверяет наличие, byte size и SHA-256 всех payload files;
- сравнивает inventory с целевым storage и показывает по каждой модели один из статусов: `new`, `already_identical`, `tag_conflict`, `invalid`, `runtime_incompatible`;
- рассчитывает необходимое место на целевом томе и явно отделяет free-space failure от package corruption.

Пакет с новым major schema, битым JSON, неразрешённым path, лишним executable/symlink, checksum mismatch или отсутствующим blob не импортируется вообще.

### Применение

После отдельного confirm import service вновь берёт transfer lock и повторяет inspect (защита от замены носителя). Он не меняет manifest-ы Ollama до тех пор, пока все требуемые blobs модели не скопированы и проверены.

1. Для `already_identical` ничего не копируется; результат отмечается как skipped.
2. Новые immutable files копируются во временную sibling-папку целевого provider root, hash проверяется, затем файл атомарно publish-ится. Existing file с тем же path допустим только при полностью совпадающем digest/size.
3. Для Ollama blobs публикуются до manifest. Manifest выбранного model tag публикуется атомарным rename последним; именно это делает модель discoverable. Общие blobs не удаляются.
4. Для ASR/Piper provider unit публикуется только после валидации набора: model directory для faster-whisper, GGML/CoreML set для whisper.cpp, ONNX+JSON для Piper.
5. Если выполнение прервано, целевые уже опубликованные valid units остаются usable и отражаются в report; без manifest/complete unit частичные данные не считаются установленной моделью. Cleanup не удаляет ничего вне task-created staging area.
6. После copy выполняется штатная discovery-проверка: Ollama storage inspection и runtime list/show; `list_local_models()` для ASR; Piper `list_voices()`/health для TTS. Только прошедшие эту проверку получают `imported`.

### Конфликты и rollback

- Повторный import одинаковой модели идемпотентен: она пропускается без переписывания.
- Если Ollama tag уже указывает на другой manifest, default — `tag_conflict` и остановка этой модели. UI предлагает сохранить существующую версию либо явно «Заменить тег»; замена требует отдельного confirmation и никогда не удаляет shared blobs.
- Для ASR/Piper collision с несовпадающими bytes default — `conflict`; overwrite не входит в MVP.
- Полноценная атомарность всего набора моделей невозможна без удвоения диска. Гарантия MVP — атомарность одной discoverable model unit и отсутствие состояния partial-as-installed.

## UX и API

Новый Settings subtab: **Models → Transfer**. UI использует существующие модели/ASR/TTS inventory, но не дублирует provider discovery на клиенте.

### Export UI

- cards/таблица с type, model/voice name, размером, complete/partial state; partial недоступны для выбора с объяснением;
- имя bundle и выбор моделей; доступны «Выбрать все готовые» и индивидуальная выборка; default — все complete models, но пользователь может снять выбор;
- до запуска: total unique size, excluded artifacts, предупреждение о необходимом свободном месте и о том, что export не удаляет источник;
- progress: current artifact, bytes/files, speed, elapsed, cancel, recoverable «диск отключён»;
- успех: точное имя bundle, checksum summary, действие «Показать безопасные инструкции для второго профиля».

Если не нужно переносить всю библиотеку за раз, пользователь создаёт несколько независимых bundles с разными selection и импортирует их по очереди.

### Import UI

- выбор готового `.localgpt-models` через browser file picker;
- preview/inspect до кнопки import, с model-by-model action и enough-space result;
- tag replacement — отдельный чекбокс + confirmation с точным model name;
- progress и итоговый report: imported/skipped/conflicted/failed, никаких ложных success toast;
- после success обновляются те же model/voice/ASR cards, что пользователь видит сегодня.

### API contract v1

Все endpoints находятся в feature router `backend/apps/model_transfer/`, а `backend/server.py` только регистрирует router. Transfer logic, archive validation, manifest parsing и transaction journal живут в service/repository, а не в HTTP router.

| Endpoint | Назначение |
| --- | --- |
| `GET /model-transfer/export-preview` | inventory и unique-size plan для выбранных installed models |
| `POST /model-transfer/exports` | создать export task по explicit selection |
| `GET /model-transfer/exports/{task_id}/download` | скачать готовый `.localgpt-models` |
| `GET /model-transfer/tasks/{task_id}` | persisted progress/report task |
| `POST /model-transfer/tasks/{task_id}/cancel` | запросить безопасную отмену |
| `POST /model-transfer/import-inspect` | загрузить bundle, validate/plan без записи в model storage |
| `POST /model-transfer/imports` | подтверждённый import по bundle ID и explicit conflict decisions |

Transfer API не принимает filesystem paths. Export response является download, import принимает только выбранный file payload; archive entries проходят строгую path validation.

Task state сохраняется в SQLite с типом, phase, progress, error code, safe report metadata и terminal state. Он не хранит manifest contents с абсолютными путями. После restart backend незавершённая задача reconciliation-ом становится `interrupted`; пользователь повторяет оборванный download/upload.

## Ошибки и сообщения

Стабильные error codes: `insufficient_destination_space`, `bundle_incomplete`, `bundle_invalid`, `bundle_checksum_mismatch`, `unsupported_bundle_version`, `unsafe_bundle_path`, `source_model_partial`, `source_model_busy`, `target_conflict`, `model_transfer_in_progress`, `provider_validation_failed`, `task_interrupted`.

Сообщение пользователю должно называть модель и действие: например, «Не импортировано `qwen3:8b`: тег уже указывает на другую версию. Существующая модель не изменена.» Нельзя сводить checksum conflict, отсутствие места и неисправный runtime к одному общему «импорт не удался».

## Security и integrity requirements

- SHA-256 вычисляется для каждого payload file и сверяется до publish на import; filename Ollama blob дополнительно сверяется с declared SHA-256 digest.
- JSON parsing ограничен разумным размером; manifest schema строгая и versioned. Неиспользуемые unknown fields можно игнорировать только в том же major version.
- Разрешены только regular files и POSIX-relative paths без `..`, absolute root, NUL и path separators, не соответствующих текущей OS.
- Export/import не запускает package content, не восстанавливает permissions/executable bit, не применяет `.env` и не изменяет profile settings.
- Логи и task reports не должны содержать исходные user-home paths, token или полный directory inventory.
- Upload/download используют bounded memory; временные файлы создаются только в backend-owned staging и удаляются после terminal state/cleanup.

## Acceptance criteria

1. Пользователь может скачать выбранные complete Ollama, faster-whisper, whisper.cpp или Piper модели одним bundle и импортировать его в другом профиле macOS/Windows, не копируя руками provider directories.
2. Export никогда не включает partial blobs/downloads, user data, secrets, executables или произвольные cache files.
3. Импорт битого/неполного/подменённого package не меняет target model storage.
4. Для каждого copied file проверены size и SHA-256; Ollama model не становится discoverable до publication всех referenced blobs и manifest.
5. При нехватке места, отключении drive или конфликте user получает конкретный recovery path; existing models не удаляются.
6. Повторный import того же package идемпотентен; shared Ollama blobs не дублируются.
7. Operation доступна из активного `web_ui/gui_html.html` / `web_ui/js/app.js`, имеет keyboard-accessible controls, focus/error state, dark/light и desktop/mobile check.
8. Transfer router не принимает arbitrary filesystem paths и не становится файловым API для LAN client без loopback/admin-token protection.
9. После import UI показывает только модели, прошедшие existing provider discovery/runtime validation.
10. Документация явно говорит, что bundle не сжимает веса существенно и требует места, сопоставимого с выбранными уникальными файлами.

## План реализации

### Stage 1 — Contract and read-only inventory

- Создать `backend/apps/model_transfer/` с schemas, strict bundle manifest parser, provider adapters и test fixtures.
- Реализовать read-only inventory/preview: reuse existing `app.services.models` Ollama inspection, ASR local model list и Piper voice list; формализовать canonical artifact set каждого provider.
- Добавить transfer task schema/migration и lock policy, но без UI write actions.
- Tests: valid/invalid manifests, traversal/symlink rejection, partial Ollama, shared blobs, size plan, config-path overrides.

### Stage 2 — Export

- Реализовать streamed ZIP64 export/hash, browser download, cancel/report и cleanup временного archive.
- Добавить export endpoints и minimal UI preview/progress.
- Tests: exact export inventory for all four families, insufficient temporary space, interruption simulation, byte/hash mismatch, no unwanted files.

### Stage 3 — Import

- Реализовать inspect, staged provider-unit copy, conflict policies, Ollama manifest-last publish и post-import validation.
- Добавить import UI, task recovery и model cards refresh.
- Tests: clean import, idempotence, blob dedupe, tag conflict, no publication on checksum failure, ASR/Piper set validation, runtime/discovery failure report.

### Stage 4 — QA, documentation and future decision

- Провести baseline/static tests, targeted backend tests и manual UI matrix: desktop/mobile, dark/light, keyboard, cancellation и большие browser download/upload на macOS и Windows.
- Обновить `README.md`, `docs/ARCHITECTURE.md`, `docs/knowledge/providers.md`, `docs/knowledge/backend.md`, `docs/knowledge/ui.md`, `docs/TESTING.md`, `docs/CHANGELOG.md` только если фактическая реализация делает эти документы неполными.
- Не добавлять volume discovery, filesystem-format policy или Shared model drive.

## Resolved decisions

1. Export/import uses one uncompressed ZIP64 `.localgpt-models` file through browser download/upload; backend destination paths and volume discovery are absent.
2. Byte-valid offline import is allowed, but UI reports `runtime_incompatible` until Ollama discovery confirms readiness.
3. Shared model drive and filesystem-format policy are excluded entirely.

## Progress Tracking Requirement

Implementation agent must first resolve the project-specific progress path (`docs/progress/`), preserve `docs/progress/.gitkeep`, and keep every other file in that directory ignored by default. Before changing source, create exactly one temporary `docs/progress/<task-name>-progress.md` and explicitly add it to each relevant stage commit. Update it after material implementation, decisions, validation and checkpoints; when handing off, include a continuation prompt with state, changes, risks, checkpoint and next action. Update only the permanent documents actually affected by the implementation, append one concise completed-task entry to `documentation/change-index.md` if that project record is introduced by the governing workflow, and delete the temporary progress file in the final cleanup commit after genuine completion. The LocalGPT `AGENTS.md` takes precedence where it differs; in particular use its `docs/` documentation ownership and do not create unrelated documentation trees.

## Git Workflow

For every implementation stage that changes tracked files, run its validation gate, inspect the staged diff, then make one focused checkpoint commit containing that stage and the current progress file. In the subsequent progress update record the prior checkpoint hash, message, changed files and validation; do not amend merely to write its own hash. Do not commit zero-change research stages. After all approved implementation and affected permanent documentation updates, create a separate final cleanup commit that removes only the completed progress file and required final documentation/index updates. Fix later defects in safe focused commits; do not rewrite shared/pushed history or use destructive Git recovery.
