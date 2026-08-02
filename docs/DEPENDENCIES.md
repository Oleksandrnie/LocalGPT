# Зависимости LocalGPT

Этот документ фиксирует результат аудита runtime-зависимостей. Источники проверки: Python imports и subprocess-вызовы в `app/` и `backend/`, активный launcher `run_localgpt.py`, статический frontend, plugin manifests, `.env.example`, networking/build scripts и test commands.

## Уровни зависимостей

| Уровень | Компонент | Версия / контракт | Для чего нужен | До setup |
| --- | --- | --- | --- | --- |
| Setup / bootstrap | macOS, Linux или Windows | native Terminal/PowerShell и Python 3.10+ для общего core | запуск platform entry point и `setup/setup_localgpt.py` | entry point устанавливает Python при отсутствии, затем передаёт управление core |
| Core | Homebrew, apt, dnf, pacman, zypper или winget | актуальная поддерживаемая версия | установка отсутствующих системных пакетов | определяется автоматически; Homebrew может быть установлен интерактивно |
| Core | Python | 3.10+ | launcher, FastAPI backend, providers, RAG и plugins | устанавливается интерактивно через Homebrew |
| Core | `venv`, `pip` | из выбранного Python | изолированное Python-окружение | создаётся/обновляется setup |
| Core LLM runtime | Ollama CLI/service | актуальная поддерживаемая версия с `/api/chat`, `/api/pull`, `/api/ps` | chat, model discovery/download и vision | устанавливается интерактивно; модели не загружаются |
| Media | FFmpeg | 6+; проверен проектный host 8.1.1 | ASR audio conversion, OCR video-frame extraction, TTS speed processing | устанавливается интерактивно |
| OCR | Tesseract | 5+; проверен project host 5.5.2 | image OCR; недоступные language packs отбрасываются runtime-ом | устанавливается интерактивно |
| ASR build | Git, CMake, Apple Command Line Tools, curl, unzip | Git 2+, CMake 3.20+ | macOS-сборка `whisper-cli`; получение ASR artifacts по явному действию пользователя | на macOS setup собирает CLI без моделей; Homebrew packages ставятся интерактивно, CLT запрашиваются macOS |
| LAN optional | Caddy | 2+; проверен project host 2.10.2 | `start_localgpt_lan.command`, private LAN HTTPS | отдельное интерактивное согласие |
| Tailnet optional | Tailscale app/CLI | 1+ | read-only plugin status и manual Tailscale Serve | отдельное интерактивное согласие; Serve/Funnel не включаются |
| QA only | Node.js | 18+ | `node --check` и `.mjs` tests | отдельное интерактивное согласие; frontend runtime Node не использует |

Жёсткий minimum для Ollama, Homebrew и Tailscale не зафиксирован кодом или manifest-ом проекта. Setup (bootstrap) поэтому проверяет работоспособный CLI и устанавливает текущую stable-версию package manager-а, не имитируя неподтверждённую совместимость со старыми версиями.

## Python packages

Канонический список прямых Python-зависимостей — [`app/requirements.txt`](../app/requirements.txt). Версии закреплены по проверенному окружению проекта, чтобы новый computer не собирал произвольную комбинацию несовместимых latest-релизов.

| Пакет | Использование |
| --- | --- |
| FastAPI, Uvicorn, python-multipart | HTTP API, static UI, uploads/forms |
| python-dotenv | `.env` parsing |
| OpenAI, HTTPX | OpenAI-compatible/Ollama HTTP clients и downloads |
| faster-whisper, huggingface-hub | ASR fallback и model artifact downloads |
| piper-tts, pydub | TTS runtime и audio handling |
| Pillow | image validation, normalization, thumbnails и OCR preprocessing |
| openpyxl | criteria import from `.xlsx` |

Transitive packages (`pydantic`, `starlette`, `ctranslate2`, `onnxruntime`, `numpy`, `av` и другие) устанавливаются resolver-ом из закреплённых direct requirements. Отдельного npm install нет: активный frontend — browser-native HTML/CSS/ES modules и не имеет `package.json`.

## Модели и данные не являются setup-зависимостями

Setup не устанавливает:

- Ollama text/vision models;
- GGML или faster-whisper models и CoreML encoder;
- Piper voices;
- RAG sources, profile/user configuration или databases.

Модельные artifacts загружаются только после явного действия в UI или отдельной model-specific команде. На macOS setup отдельно собирает native `whisper-cli` без GGML-модели и CoreML encoder; для Linux и Windows он пока не запускает непроверенную native-сборку.

## Переменные окружения

Обязательных пользовательских переменных для первого локального запуска нет: defaults позволяют создать storage и поднять backend. `.env` опционален и setup его не создаёт и не меняет.

Основные группы overrides полностью перечислены в [`.env.example`](../.env.example):

- model/storage paths: `MODELS_DIR`, `OLLAMA_MODELS_DIR`, `WHISPER_MODELS_DIR`, `WHISPER_CPP_MODELS_DIR`, `TTS_MODELS_DIR`, `PIPER_MODELS_DIR`, cache/data paths;
- providers: `LOCAL_BASE_URL`, `LOCAL_API_KEY`, `LOCAL_MODEL`, `OLLAMA_HOST`, ASR/TTS/OCR settings;
- runtime/networking: `LOCALGPT_HOST`, `LOCALGPT_PORT`, remote-access flags, LAN URL/port и CORS overrides;
- optional download/auth overrides: Hugging Face tokens/endpoints and whisper.cpp repository/path settings.

Secrets и machine-specific paths не должны попадать в Git.

## Что уже автоматизировано

- `run_localgpt.py` создаёт `venv/`, устанавливает `app/requirements.txt` при изменении его hash, создаёт runtime directories, запускает Ollama service и backend.
- UI/provider flows по явному действию скачивают выбранные Ollama, ASR и Piper models.
- `setup/setup_localgpt.py` отвечает за OS/package-manager detection, интерактивную установку системных компонентов, project dependencies и итоговую проверку; на macOS он также строит и проверяет `models/whisper_cpp/bin/whisper-cli` без загрузки model artifacts. Все platform entry points и Windows PowerShell adapter находятся рядом в `setup/`; они вычисляют корень проекта от собственного пути, поэтому не зависят от текущего рабочего каталога.

Launcher запуска приложения не должен подменять setup системных пакетов: после первого setup обычный старт остаётся быстрым и идемпотентным.
