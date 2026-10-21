# Backlog

Здесь хранится только незавершённая работа. Завершённые результаты находятся в [CHANGELOG.md](CHANGELOG.md).

## Planned

- Investigate Qwen3 reasoning that was returned with `think=False`/`/no_think`; determine how the Thinking control should report provider behavior rather than trusting request settings alone.
- Добавить безопасную очистку runtime logs из Settings с подтверждением и сохранением log rotation.
- Решить, входит ли Caddy/LAN entry point в первый публичный снимок. Предпочтительный безопасный вариант — локальный запуск; сетевой доступ оставлять только вместе с общей аутентификацией API и проверкой в реальной сети.

## Technical debt

- Удалить `compare-branch/` только после отдельного parity checklist и подтверждения, что reference snapshots больше не нужны.
- Удалить legacy `LTrnsrb.*` aliases после подтверждения всех современных launcher flows.
- Завершить перенос shared/core границ из `app/` в явный backend core layer.
- Разделить большие `web_ui/js/app.js` и `web_ui/css/style.css` на поддерживаемые feature modules без смены активного entry point.

## Known issues

- Full ASR analysis может заметно нагружать CPU/GPU и требует ручного разрешения.
- Live functionality зависит от внешних binaries и локальных моделей; unit tests не подтверждают готовность конкретной машины.
- LAN HTTPS path функционально проверен в реальной сети, но Safari certificate trust остаётся отдельной device-level настройкой.

## Deferred decisions

- Создать новый публичный репозиторий из проверенного и отобранного source snapshot с новым root commit, не перенося старые Git refs. Перепись истории старого приватного репозитория не является условием этой публикации. Отдельно провести закрытую инвентаризацию исторических credentials и отозвать/заменить значения, которые действуют сейчас или чей статус неизвестен; не копировать их в задачи и документы. Новый repo сам по себе не отзывает credentials в старом.
- Перед созданием snapshot провести полный review публикуемого дерева на provenance, лицензии и остатки пробных компонентов (включая third_party — сначала установить точное название/проект): source и imports, dependency manifests/lockfiles, installer/build scripts, configs, plugin manifests, UI, docs, assets и binaries. Удалить связанные неиспользуемые код, файлы, зависимости и упоминания; повторить поиск и проверить лицензии всех оставшихся распространяемых компонентов. Отдельно отобрать публичную документацию: не переносить внутренний backlog/security audit с историей и служебными деталями без редакторской чистки.
- Владелец подтвердил намерение выпустить собственный код LocalGPT под GPL-3.0-or-later. Перед публикацией проверить, что в snapshot нет кода, на который права принадлежат третьим лицам, и подготовить корректные notices для всех зависимостей. Текущий корневой `License` старого checkout остаётся All Rights Reserved до отдельного изменения.
- Piper runtime package распространяется под GPL-3.0-or-later, но лицензия Piper не распространяется автоматически на голоса и модели. Для каждого включаемого/раздаваемого артефакта проверить его собственные условия и происхождение; для Ryan low отдельно разрешить неоднозначность между лицензией датасета в model card и лицензией самого model artifact.
- Для первого публичного snapshot по умолчанию оставить только локальный entry point и исключить Caddy/LAN UI, launchers и поддержку, если сетевой режим не нужен. Если LAN оставить, спроектировать общую аутентификацию API и проверить её вместе с реальным сетевым сценарием; простой bind на `0.0.0.0` не заменяет эту защиту.
- Закрепить install/build sources и checksums, добавить transitive dependency lock strategy и artifact license/provenance metadata.
- Выполнить clean install, model setup и restart/persistence/shutdown smoke на каждом OS, который будет заявлен поддерживаемым; сейчас кроссплатформенные entry points ещё не подтверждены end-to-end.
- Выбрать приватный security disclosure channel до открытия публичных issue/PR.

- Direct Hugging Face chat inference and a UI flow for local Safetensors/GGUF import (`Modelfile` / `ollama create`) remain separate from the current Ollama-only runtime and guarded `ollama pull` installer. HF-origin models are supported by this work only after they are installed into Ollama and expose `/api/show` thinking metadata.
- External plugin process API требует отдельного security design: isolation, permissions, IPC, lifecycle, timeouts и audit.
- Plugin marketplace требует signing, trust, review, update и rollback model.
- Hot reload arbitrary plugin code не поддерживается; текущая Registry v0 остаётся metadata-only.
- ASR, TTS, RAG, OCR и chat не мигрируются в plugins без отдельного архитектурного решения.
