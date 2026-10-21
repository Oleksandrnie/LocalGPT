# Backlog

Здесь хранится только незавершённая работа. Завершённые результаты находятся в [CHANGELOG.md](CHANGELOG.md).

## Planned

- Выполнить отдельную реальную Tailscale/tailnet validation; LAN Caddy HTTPS → localhost backend уже проверен с другого устройства в private Wi-Fi.
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
- LAN HTTPS path функционально проверен в реальной сети, но Safari certificate trust остаётся отдельной device-level настройкой; Tailscale availability проверяется только в реальной tailnet-среде.

## Deferred decisions

- Перед публичной публикацией приватно оценить и удалить чувствительные credential/chat-data blobs из доступной Git history после ротации действительных значений; требуются owner approval и независимая проверка после rewrite.
- Выбрать project license и проверить совместимость с direct GPL Piper dependency и лицензиями каждой распространяемой модели/голоса; root `License` остаётся All Rights Reserved до решения владельца.
- Спроектировать общую аутентификацию для API-клиентов LAN/Tailscale либо не включать эти entry points в release; `ADMIN_TOKEN` не является глобальной caller identity.
- Закрепить install/build sources и checksums, добавить transitive dependency lock strategy и artifact license/provenance metadata.
- Выполнить clean install, model setup и restart/persistence/shutdown smoke на каждом OS, который будет заявлен поддерживаемым; сейчас кроссплатформенные entry points ещё не подтверждены end-to-end.
- Выбрать приватный security disclosure channel до открытия публичных issue/PR.

- Direct Hugging Face chat inference and a UI flow for local Safetensors/GGUF import (`Modelfile` / `ollama create`) remain separate from the current Ollama-only runtime and guarded `ollama pull` installer. HF-origin models are supported by this work only after they are installed into Ollama and expose `/api/show` thinking metadata.
- External plugin process API требует отдельного security design: isolation, permissions, IPC, lifecycle, timeouts и audit.
- Plugin marketplace требует signing, trust, review, update и rollback model.
- Hot reload arbitrary plugin code не поддерживается; текущая Registry v0 остаётся metadata-only.
- ASR, TTS, RAG, OCR и chat не мигрируются в plugins без отдельного архитектурного решения.
