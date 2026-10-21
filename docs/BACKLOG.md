# Backlog

Здесь хранится только незавершённая работа. Завершённые результаты находятся в [CHANGELOG.md](CHANGELOG.md).

## Planned

- Investigate Qwen3 reasoning that was returned with `think=False`/`/no_think`; determine how the Thinking control should report provider behavior rather than trusting request settings alone.
- Добавить безопасную очистку runtime logs из Settings с подтверждением и сохранением log rotation.
- Рассмотреть metadata/trusted-handler модель для Caddy без изменения существующего LAN fast path.

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

- Подготовить новый публичный репозиторий из проверенного исходного снимка без копирования прежних Git refs; текущий репозиторий и его историю оценить отдельно, включая ротацию действительных credentials. Новый repo не очищает уже существующие remote refs, PR refs, forks, clones или caches.
- Для нового публичного репозитория владелец планирует GPL-3.0-or-later; до публикации подтвердить права на relicensing всех включённых компонентов и проверить лицензии распространяемых Piper voices/models. Текущий корневой `License` остаётся All Rights Reserved до отдельного изменения.
- Спроектировать общую аутентификацию для API-клиентов LAN либо не включать этот entry point в release; `ADMIN_TOKEN` не является глобальной caller identity.
- Закрепить install/build sources и checksums, добавить transitive dependency lock strategy и artifact license/provenance metadata.
- Выполнить clean install, model setup и restart/persistence/shutdown smoke на каждом OS, который будет заявлен поддерживаемым; сейчас кроссплатформенные entry points ещё не подтверждены end-to-end.
- Выбрать приватный security disclosure channel до открытия публичных issue/PR.

- Direct Hugging Face chat inference and a UI flow for local Safetensors/GGUF import (`Modelfile` / `ollama create`) remain separate from the current Ollama-only runtime and guarded `ollama pull` installer. HF-origin models are supported by this work only after they are installed into Ollama and expose `/api/show` thinking metadata.
- External plugin process API требует отдельного security design: isolation, permissions, IPC, lifecycle, timeouts и audit.
- Plugin marketplace требует signing, trust, review, update и rollback model.
- Hot reload arbitrary plugin code не поддерживается; текущая Registry v0 остаётся metadata-only.
- ASR, TTS, RAG, OCR и chat не мигрируются в plugins без отдельного архитектурного решения.
