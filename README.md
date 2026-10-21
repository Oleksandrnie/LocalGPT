# LocalGPT

LocalGPT — локальное приложение для чата, транскрибации, синтеза речи, OCR и RAG. Данные, модели и runtime-артефакты остаются на компьютере; основной интерфейс доступен в браузере через FastAPI.

## Возможности

- чат с профилями, историей, streaming-ответами, image attachments и локальными text/vision Ollama-моделями;
- Auto / Smart Router для выбора chat-модели по типу запроса;
- ASR Studio и быстрый voice-to-input через whisper.cpp или faster-whisper;
- анализ транскриптов: быстрое саммари, умное саммари и явно разрешаемый полный pipeline;
- Voice Studio на базе Piper с локальной библиотекой голосов и историей;
- OCR изображений через Tesseract;
- profile-scoped RAG для Markdown-файлов, включая ASR context и явно сохраняемый text-only Vision context;
- перенос complete Ollama, faster-whisper, whisper.cpp и Piper моделей между установками через один `.localgpt-models` bundle;
- Plugin Registry v0 с trusted backend handlers;
- локальный, LAN и private-tailnet доступ.

## Стек

- Python, FastAPI, Uvicorn, SQLite;
- Ollama / OpenAI-compatible API для chat-моделей;
- whisper.cpp и faster-whisper для ASR;
- Piper для TTS;
- Tesseract для OCR;
- статический Web UI на HTML, CSS и JavaScript;
- Caddy для LAN HTTPS;
- Tailscale Serve для опционального private-tailnet доступа.

## Первый запуск проекта

На новом компьютере запустите platform entry point. Он определит ОС и package manager, откроет Terminal/PowerShell, покажет отсутствующие компоненты и запросит согласие перед каждой установкой.

macOS — двойной клик по `setup/setup_localgpt.command` или команда:

```bash
./setup/setup_localgpt.command
```

Linux:

```bash
./setup/setup_localgpt.sh
```

Windows — двойной клик по `setup\setup_localgpt.bat`. Он откроет PowerShell и продолжит установку там.

Setup (технически — bootstrap):

- при необходимости устанавливает Python и поддерживаемый package manager;
- ставит обязательные system/runtime tools и закреплённые Python packages в `venv/`;
- отдельно предлагает опциональные Caddy, Tailscale и Node.js;
- на macOS собирает штатный `whisper-cli` и небольшой Silero VAD-фильтр от распознавания тишины, но не загружает ASR-модели и CoreML-артефакты;
- безопасно пропускает уже найденные компоненты и пригоден для повторного запуска;
- не скачивает модели, RAG-данные, не создаёт `.env` и не включает сетевой доступ.

Канонический список Python packages находится в `app/requirements.txt`; отдельного корневого `requirements.txt` нет. Setup создаёт штатный `venv/`. Если ранее было вручную создано `.venv/`, оно останется нетронутым, но LocalGPT его не использует.

После успешной финальной проверки запускайте LocalGPT обычным launcher-ом из следующего раздела. Полный подтверждённый inventory, версии и назначение компонентов: [Зависимости LocalGPT](docs/DEPENDENCIES.md).

## Требования и ограничения

Для runtime используются:

- Python 3.11+;
- достаточно свободного диска под выбранные модели;
- Ollama для LLM-функций.

По используемым функциям:

- `ffmpeg` — конвертация аудио и часть ASR/TTS сценариев;
- `whisper-cli` (собирается setup-ом на macOS) и GGML-модель — для backend `whisper_cpp`;
- Tesseract — для OCR;
- Caddy — для штатного LAN HTTPS launcher на macOS;
- Tailscale — только для private-tailnet доступа.

## Обычный запуск

1. При необходимости создайте локальную конфигурацию:

   ```bash
   cp .env.example .env
   ```

   Задайте в `.env` непустой случайный `ADMIN_TOKEN`, если нужны restart/shutdown, database cleanup/reset, изменение model storage paths или защищённая prompt/runtime diagnostics. Web UI запрашивает его только при такой операции и хранит лишь до закрытия browser session.

2. Запустите приложение:

   macOS / Linux:

   ```bash
   ./start_localgpt.sh
   ```

   Windows:

   ```bat
   start_localgpt.bat
   ```

   macOS `.command`:

   ```text
   start_localgpt.command
   ```

Launcher повторно использует подготовленный `venv/`, при изменении `app/requirements.txt` обновляет packages, проверяет Ollama, выбирает свободный backend-порт и запускает `backend.server:app`. На macOS обычный запуск без аргументов также автоматически поднимает Caddy для private LAN HTTPS, сохраняя backend на localhost; URL появится в разделе «Доступ с телефона». Если Caddy не установлен или private LAN IP отсутствует, LocalGPT явно сообщит об этом и откроет только локальный UI. Linux/Windows и macOS-запуск с явными аргументами остаются direct local launch. Если порт занят, launcher выбирает следующий свободный.

Команда `python3 run_localgpt.py` также поддерживается: если системный `python3` старее 3.11, launcher автоматически продолжит через подготовленный `venv/bin/python`. Системный Python при этом не изменяется.

Полезные варианты:

```bash
venv/bin/python run_localgpt.py --no-browser
venv/bin/python run_localgpt.py --no-reload
venv/bin/python run_localgpt.py --host 127.0.0.1 --port 8000 --strict-port
```

Параметры окружения, `ADMIN_TOKEN`, model paths, CORS и ASR/TTS настройки перечислены в [`.env.example`](.env.example).

## LAN и Tailscale

Для доступа в одной локальной сети на macOS используйте обычный `start_localgpt.command` или `./start_localgpt.sh` без аргументов: LAN launcher теперь запускается автоматически. `start_localgpt_lan.command` сохранён как compatibility alias. LAN path оставляет backend на localhost и поднимает Caddy HTTPS на локальном адресе. Подробности и диагностика: [networking](docs/knowledge/networking.md).

Для удалённого доступа используйте только private Tailscale tailnet. LocalGPT не запускает `tailscale serve` автоматически и не рекомендует Funnel или прямую публикацию backend-порта. Инструкция находится в [Tailscale plugin](plugins/tailscale/README.md).

## Данные и модели

Основные локальные пути:

- `models/ollama/` — chat-модели;
- `models/whisper/` и `models/whisper_cpp/` — ASR;
- `models/tts/piper/` — Piper voices;
- `models/hf_cache/` и `models/ctranslate2_cache/` — кэши;
- `app/db/localgpt.db` — SQLite;
- `rag_sources/profile-<id>/` — документы профиля;
- `app/data/chat_attachments/profile-<id>/` — оригиналы и thumbnails chat-изображений;
- `app/data/tts/` и `tmp_logs/` — runtime-артефакты.

Эти данные игнорируются Git. Пустая `LOCAL_MODEL` допустима: приложение запускается без chat-модели, а загрузка выполняется только по явному действию пользователя.

## Документация

- [Индекс документации](docs/README.md)
- [Архитектура](docs/ARCHITECTURE.md)
- [Тестирование](docs/TESTING.md)
- [Зависимости и setup](docs/DEPENDENCIES.md)
- [Экспорт и импорт моделей](docs/MODEL_TRANSFER_SPEC.md)
- [Backlog](docs/BACKLOG.md)
- [Инструкции для coding-агентов](AGENTS.md)

Подробности подсистем находятся в [`docs/knowledge/`](docs/knowledge/). Runtime prompt остаётся рядом с кодом: [`app/prompts/system_base.md`](app/prompts/system_base.md).
