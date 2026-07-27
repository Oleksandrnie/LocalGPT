# ТЗ: безопасный перенос локальных моделей

## Статус и цель

Статус: согласованное ТЗ для реализации, функциональность пока не реализована.

Нужно дать пользователю LocalGPT безопасный способ перенести установленные модели между независимыми профилями macOS и Windows. Перенос должен выполняться из интерфейса LocalGPT через подключённый внешний носитель, не требовать ручного поиска runtime-папок и не оставлять принимающий профиль в состоянии «модель видна, но не запускается».

Основной пользовательский сценарий:

1. В профиле-источнике пользователь открывает Settings → Models → «Перенос моделей», выбирает установленные модели и внешний диск.
2. LocalGPT создаёт переносимый пакет, проверяет каждый записанный файл и показывает его размер и результат.
3. В профиле-получателе пользователь подключает диск, открывает «Импорт», выбирает готовый пакет, видит предварительный план и подтверждает импорт.
4. LocalGPT проверяет пакет и место, устанавливает модели в configured model paths этого профиля и повторно проверяет их штатными discovery-процедурами.

## Важное ограничение

Архив не может уменьшить физически необходимое место: веса LLM, GGML и ONNX уже в основном сжаты. Экспорт занимает не меньше суммы уникальных выбранных файлов плюс небольшой служебный overhead. Дедупликация общих Ollama blobs уменьшает размер только тогда, когда несколько выбранных тегов используют один и тот же blob.

Если флешка не вмещает пакет, корректные варианты — внешний SSD/HDD достаточного объёма или будущий режим **Shared model drive**, в котором оба профиля используют один каталог моделей на внешнем SSD и модели не копируются вовсе. Этот режим не входит в MVP импорта/экспорта и требует отдельного UX для подключения storage path и межпрофильной блокировки. Носитель для кроссплатформенного переноса должен быть отформатирован в exFAT: FAT32 не подходит, потому что один model blob может быть больше 4 GiB.

## Scope

### Входит в MVP

- Экспорт и импорт полных, локально установленных артефактов следующих provider families:
  - Ollama chat/vision models;
  - faster-whisper model directories, найденных штатным ASR discovery;
  - whisper.cpp GGML/CoreML model assets;
  - Piper voice pairs (`.onnx` и соответствующий `.onnx.json`).
- Выбор конкретных моделей, preview объёма, дедупликация Ollama blobs, прогресс, отмена, повторный запуск после отключения носителя и понятный отчёт.
- Целостность файлов, безопасная публикация модели только после проверки, проверка свободного места и provider-specific post-import discovery.
- Импорт в текущие configured paths из `app.config.MODEL_PATHS`; absolute paths профиля-источника, имена macOS/Windows account и Windows drive letters не переносятся.

### Не входит в MVP

- Загрузка моделей через браузер в память/HTTP upload и передача package по LAN.
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

### Почему bundle-directory, а не ZIP по умолчанию

MVP использует один переносимый каталог с расширением `.localgpt-models`, например `LocalGPT-models-2026-07-27.localgpt-models`. Он записывается напрямую на выбранный внешний том без промежуточной копии в домашнюю папку и без сжатия.

Это уменьшает потребность во временном свободном месте, позволяет возобновлять copy по файлам и не тратит часы CPU на практически бесполезное сжатие моделей. Опциональный read-only export в PAX tar допускается позднее только как transport wrapper вокруг готового bundle; импорт сначала распаковывает/проверяет wrapper и применяет те же правила bundle v1.

### Структура пакета

```text
<name>.localgpt-models/
  manifest.json                 # write last; schema/model inventory/checksums
  READY                         # zero-byte final completion marker
  .transfer-state.json          # temporary, удаляется при успехе
  payload/
    ollama/
      manifests/<original relative path>
      blobs/sha256-...
    faster-whisper/<model id>/<relative path>
    whisper-cpp/<model id>/<relative path>
    piper/<voice id>/<relative path>
```

`manifest.json` — UTF-8 JSON, schema `localgpt-model-bundle`, version `1`. Он содержит только переносимые metadata: bundle ID, время создания, минимальную версию LocalGPT, producer platform (diagnostic only), выбранные model IDs, family, provider metadata, список payload files, их POSIX-relative path, byte size и SHA-256. Для Ollama он содержит model name/tag, относительный путь manifest и список digest каждого required blob. Никаких исходных absolute paths, drive letters, токенов, profile IDs, user names или содержимого БД в manifest нет. Manifest paths обязаны быть уникальны также при case-insensitive сравнении, чтобы package одинаково работал на default macOS и Windows filesystems.

`READY` создаётся только после fsync всех payload files и записи manifest. Пакет без корректных `manifest.json` и `READY` считается незавершённым и не импортируется; UI предлагает только «возобновить экспорт» на исходном профиле или удалить incomplete package после явного подтверждения.

### Правила создания

1. Перед стартом service получает process-wide model-transfer lock. В это время pull, delete, prepare/update, preload и новый model export/import получают контролируемую ошибку `model_transfer_in_progress`.
2. Активные model tasks должны завершиться, быть отменены пользователем либо быть выгружены штатным runtime lifecycle. Экспорт не читает артефакты, пока соответствующая загрузка/обновление в progress.
3. UI показывает точный прогноз уникальных байтов, требуемый reserve (metadata + 2%), доступное место destination volume и предупреждает, если места недостаточно.
4. Service принимает не raw absolute path, а opaque ID подключённого removable volume и user-provided folder name. Он canonicalizes destination, разрешает путь только под выбранным volume root и отказывает symlink/path traversal. Platform adapter определяет volume root: `/Volumes/<name>` на macOS и root assigned removable drive (например, `E:\\`) на Windows. Для MVP допустимы только смонтированные внешние/removable volumes в exFAT.
5. Каждый source path должен быть regular file внутри допустимого provider root. Симлинки, sockets, hidden temporary artifacts, `*-partial*` и неизвестные executable files отклоняются и включаются в отчёт как excluded.
6. Файлы копируются в `<bundle>.incomplete` с ограниченным буфером; для каждого вычисляются size и SHA-256 во время записи. Возобновление сравнивает уже записанный размер и digest; совпадающий файл не копируется заново, несовпадающий перезаписывается только внутри incomplete bundle.
7. Для Ollama export сначала строит dependency graph из manifest-ов и включает каждый digest один раз. Экспорт невозможен, если выбранный model manifest не парсится или хотя бы один required blob отсутствует.
8. После успешной проверки incomplete directory атомарно переименовывается в final bundle, затем создаются `manifest.json` и `READY` в указанном порядке. Исходные модели остаются неизменными.

## Импорт

### Inspect до подтверждения

`inspect` не пишет в model storage. Он:

- находит только готовые `.localgpt-models` под выбранным external volume;
- проверяет schema version, `READY`, syntax manifest, allowed family/path set, уникальность путей и отсутствие symlink;
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
- выбор external volume, имя bundle и моделей; доступны «Выбрать все готовые» и индивидуальная выборка; default — все complete models, но пользователь может снять выбор;
- до запуска: total unique size, volume free space, excluded artifacts, предупреждение о том, что export не удаляет источник;
- progress: current artifact, bytes/files, speed, elapsed, cancel, recoverable «диск отключён»;
- успех: точное имя bundle, checksum summary, действие «Показать безопасные инструкции для второго профиля».

Если не нужно или невозможно перенести всю библиотеку за раз, пользователь создаёт несколько независимых bundles с разными selection и импортирует их по очереди. MVP не делит один blob между несколькими носителями: один выбранный model unit должен целиком помещаться на используемый exFAT drive, иначе операция не начинается. Это сохраняет resume, checksum и import atomicity простыми и проверяемыми.

### Import UI

- выбор подключённого external volume и готового bundle; запрещено вводить серверный произвольный путь;
- preview/inspect до кнопки import, с model-by-model action и enough-space result;
- tag replacement — отдельный чекбокс + confirmation с точным model name;
- progress и итоговый report: imported/skipped/conflicted/failed, никаких ложных success toast;
- после success обновляются те же model/voice/ASR cards, что пользователь видит сегодня.

### API contract v1

Все endpoints находятся в feature router `backend/apps/model_transfer/`, а `backend/server.py` только регистрирует router. Transfer logic, platform volume adapter, filesystem allowlist, manifest parsing и transaction journal живут в service/repository, а не в HTTP router.

| Endpoint | Назначение |
| --- | --- |
| `GET /model-transfer/volumes` | список допустимых внешних volumes: opaque ID, display name, filesystem, free/total bytes, availability |
| `GET /model-transfer/export-preview` | inventory и unique-size plan для выбранных installed models |
| `POST /model-transfer/exports` | создать/resume export task по volume ID, folder name и explicit selection |
| `GET /model-transfer/tasks/{task_id}` | persisted progress/report task |
| `POST /model-transfer/tasks/{task_id}/cancel` | запросить безопасную отмену |
| `GET /model-transfer/bundles?volume_id=...` | только готовые bundles этого volume |
| `POST /model-transfer/import-inspect` | validate/plan готового bundle без записи |
| `POST /model-transfer/imports` | подтверждённый import по bundle ID и explicit conflict decisions |

Transfer endpoints, которые перечисляют external volumes или читают/пишут файлы, доступны только loopback request или при валидном admin token. CORS не является контролем доступа. В LAN-сессии UI должен показать, что операцию нужно открыть локально на компьютере, где подключён диск, если token не настроен. Service не принимает raw paths от браузера и не следует symbolic links.

Task state сохраняется в SQLite с типом, phase, progress, resumable/error code, safe report metadata и terminal state. Он не хранит manifest contents с абсолютными путями. После restart backend незавершённая задача reconciliation-ом становится `interrupted`; пользователь может повторно выбрать тот же volume, и export resume проверит existing incomplete files.

## Ошибки и сообщения

Стабильные error codes: `external_volume_missing`, `insufficient_destination_space`, `bundle_incomplete`, `bundle_invalid`, `bundle_checksum_mismatch`, `unsupported_bundle_version`, `unsafe_bundle_path`, `source_model_partial`, `source_model_busy`, `target_conflict`, `model_transfer_in_progress`, `provider_validation_failed`, `task_interrupted`.

Сообщение пользователю должно называть модель и действие: например, «Не импортировано `qwen3:8b`: тег уже указывает на другую версию. Существующая модель не изменена.» Нельзя сводить checksum conflict, отсутствие места и неисправный runtime к одному общему «импорт не удался».

## Security и integrity requirements

- SHA-256 вычисляется для каждого payload file и сверяется до publish на import; filename Ollama blob дополнительно сверяется с declared SHA-256 digest.
- JSON parsing ограничен разумным размером; manifest schema строгая и versioned. Неиспользуемые unknown fields можно игнорировать только в том же major version.
- Разрешены только regular files и POSIX-relative paths без `..`, absolute root, NUL и path separators, не соответствующих текущей OS.
- Export/import не запускает package content, не восстанавливает permissions/executable bit, не применяет `.env` и не изменяет profile settings.
- Логи и task reports не должны содержать исходные user-home paths, token или полный directory inventory.
- До реализации надо проверить macOS access rules для `/Volumes`, Windows removable-drive discovery/ACL/locked files, exFAT на обеих ОС, APFS/NTFS как non-portable storage, FAT32 file-size failure, диски с недостаточными правами и eject в середине copy.

## Acceptance criteria

1. Пользователь может перенести выбранную complete Ollama, faster-whisper, whisper.cpp или Piper модель между двумя профилями macOS и/или Windows через внешний exFAT drive, не копируя руками provider directories.
2. Export никогда не включает partial blobs/downloads, user data, secrets, executables или произвольные cache files.
3. Импорт битого/неполного/подменённого package не меняет target model storage.
4. Для каждого copied file проверены size и SHA-256; Ollama model не становится discoverable до publication всех referenced blobs и manifest.
5. При нехватке места, отключении drive или конфликте user получает конкретный recovery path; existing models не удаляются.
6. Повторный import того же package идемпотентен; shared Ollama blobs не дублируются.
7. Operation доступна из активного `web_ui/gui_html.html` / `web_ui/js/app.js`, имеет keyboard-accessible controls, focus/error state, dark/light и desktop/mobile check.
8. Transfer router не принимает arbitrary filesystem paths и не становится файловым API для LAN client без loopback/admin-token protection.
9. После import UI показывает только модели, прошедшие existing provider discovery/runtime validation.
10. Документация описывает, что package не решает физическую нехватку места; для этого определён отдельный future Shared model drive decision.

## План реализации

### Stage 1 — Contract and read-only inventory

- Создать `backend/apps/model_transfer/` с schemas, strict bundle manifest parser, provider adapters и test fixtures.
- Реализовать read-only inventory/preview: reuse existing `app.services.models` Ollama inspection, ASR local model list и Piper voice list; формализовать canonical artifact set каждого provider.
- Добавить transfer task schema/migration и lock policy, но без UI write actions.
- Tests: valid/invalid manifests, traversal/symlink rejection, partial Ollama, shared blobs, size plan, config-path overrides.

### Stage 2 — Export

- Реализовать volume discovery/allowlist, incomplete bundle, streamed copy/hash, resume/cancel/report и `READY` semantics.
- Добавить export endpoints и minimal UI preview/progress.
- Tests: exact export inventory for all four families, insufficient space, disconnect/interruption simulation, resume, byte/hash mismatch, no unwanted files.

### Stage 3 — Import

- Реализовать inspect, staged provider-unit copy, conflict policies, Ollama manifest-last publish и post-import validation.
- Добавить import UI, task recovery и model cards refresh.
- Tests: clean import, idempotence, blob dedupe, tag conflict, no publication on checksum failure, ASR/Piper set validation, runtime/discovery failure report.

### Stage 4 — QA, documentation and future decision

- Провести baseline/static tests, targeted backend tests и manual UI matrix: desktop/mobile, dark/light, keyboard, cancellation, mounted exFAT drive на macOS и Windows; дополнительно проверить APFS/NTFS как local-only storage и понятный отказ для FAT32 file-size limit.
- Обновить `README.md`, `docs/ARCHITECTURE.md`, `docs/knowledge/providers.md`, `docs/knowledge/backend.md`, `docs/knowledge/ui.md`, `docs/TESTING.md`, `docs/CHANGELOG.md` только если фактическая реализация делает эти документы неполными.
- Отдельно принять/отклонить design for Shared model drive; не добавлять его неявно в export/import stage.

## Open decisions before coding

1. **MVP destination policy:** ограничиться внешними exFAT volumes, обнаруженными platform adapter (`/Volumes/<external>` на macOS, removable drive roots на Windows; рекомендуется), или разрешить user-selected local directories. Первый вариант безопаснее для LAN threat model и лучше соответствует use case.
2. **Runtime check:** будет ли import требовать установленный и запущенный Ollama сразу, либо допустит byte-valid import с `runtime_incompatible` status. Рекомендуется второе: пакет можно перенести офлайн, но UI не утверждает, что chat готов до `ollama list/show`.
3. **Shared model drive:** делать отдельным follow-up после MVP или расширить project storage settings. Рекомендуется follow-up: это меняет ownership и locking path, а не просто transport.

## Progress Tracking Requirement

Implementation agent must first resolve the project-specific progress path (`docs/progress/`), preserve `docs/progress/.gitkeep`, and keep every other file in that directory ignored by default. Before changing source, create exactly one temporary `docs/progress/<task-name>-progress.md` and explicitly add it to each relevant stage commit. Update it after material implementation, decisions, validation and checkpoints; when handing off, include a continuation prompt with state, changes, risks, checkpoint and next action. Update only the permanent documents actually affected by the implementation, append one concise completed-task entry to `documentation/change-index.md` if that project record is introduced by the governing workflow, and delete the temporary progress file in the final cleanup commit after genuine completion. The LocalGPT `AGENTS.md` takes precedence where it differs; in particular use its `docs/` documentation ownership and do not create unrelated documentation trees.

## Git Workflow

For every implementation stage that changes tracked files, run its validation gate, inspect the staged diff, then make one focused checkpoint commit containing that stage and the current progress file. In the subsequent progress update record the prior checkpoint hash, message, changed files and validation; do not amend merely to write its own hash. Do not commit zero-change research stages. After all approved implementation and affected permanent documentation updates, create a separate final cleanup commit that removes only the completed progress file and required final documentation/index updates. Fix later defects in safe focused commits; do not rewrite shared/pushed history or use destructive Git recovery.
