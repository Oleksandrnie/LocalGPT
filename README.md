# LocalGPT

LocalGPT — локальное приложение для чата, транскрибации, синтеза речи, OCR и RAG. Данные, модели и runtime-артефакты остаются на компьютере; основной интерфейс доступен в браузере через FastAPI.

## Возможности

- чат с профилями, историей, streaming-ответами, image attachments и локальными text/vision Ollama-моделями;
- Auto / Smart Router для выбора chat-модели по типу запроса;
- ASR Studio и быстрый voice-to-input через whisper.cpp или faster-whisper;
- анализ транскриптов: быстрое саммари, умное саммари и явно разрешаемый полный pipeline;
- Voice Studio на базе Piper с локальной библиотекой голосов и историей;
- OCR изображений через Tesseract;
- profile-scoped RAG для `.txt`, `.md` и `.json`, включая ASR context и явно сохраняемый text-only Vision context;
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

## Требования

Обязательно:

- Python 3;
- достаточно свободного диска под выбранные модели;
- Ollama для LLM-функций.

По используемым функциям:

- `ffmpeg` — конвертация аудио и часть ASR/TTS сценариев;
- `whisper-cli` и GGML-модель — для backend `whisper_cpp`;
- Tesseract — для OCR;
- Caddy — для штатного LAN HTTPS launcher на macOS;
- Tailscale — только для private-tailnet доступа.

## Быстрый запуск

1. При необходимости создайте локальную конфигурацию:

   ```bash
   cp .env.example .env
   ```

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

Launcher создаёт `venv/`, устанавливает `app/requirements.txt`, проверяет Ollama, выбирает свободный backend-порт и запускает `backend.server:app`. По умолчанию UI открывается на `http://127.0.0.1:8000/ui/gui_html.html`; если порт занят, launcher выбирает следующий свободный.

Полезные варианты:

```bash
python3 run_localgpt.py --no-browser
python3 run_localgpt.py --no-reload
python3 run_localgpt.py --host 127.0.0.1 --port 8000 --strict-port
```

Параметры окружения, model paths, CORS и ASR/TTS настройки перечислены в [`.env.example`](.env.example).

## LAN и Tailscale

Для доступа в одной локальной сети на macOS:

```text
start_localgpt_lan.command
```

LAN launcher оставляет backend на localhost и поднимает Caddy HTTPS на локальном адресе. Подробности и диагностика: [networking](docs/knowledge/networking.md).

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
- [Backlog](docs/BACKLOG.md)
- [Инструкции для coding-агентов](AGENTS.md)

Подробности подсистем находятся в [`docs/knowledge/`](docs/knowledge/). Runtime prompt остаётся рядом с кодом: [`app/prompts/system_base.md`](app/prompts/system_base.md).
