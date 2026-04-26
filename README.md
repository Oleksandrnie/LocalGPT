# LocalGPT

Локальный unified-проект для `chat + ASR + TTS + OCR + LAN + RAG` без внешних облачных API.
Основной runtime работает на `FastAPI + Ollama + faster-whisper + Piper + Tesseract + SQLite`.

## Что уже есть

- `backend/apps/*` mini-app layout для chat/asr/tts/ocr (transitional migration от legacy `app/...`);
- локальный чат с историей, профилями и model settings;
- profile-scoped RAG:
  отдельная папка документов на каждый профиль, ручная индексация, JSON как source of truth, Markdown как пояснение;
- profile-level system prompt, который подмешивается в prompt только для активного профиля;
- summary memory для длинных диалогов:
  старое raw history не обязано целиком попадать в prompt, `mem_turns` остаётся short-term window;
- `ASR Studio` для отдельной транскрибации файлов:
  история, редактирование, pipeline-обработка, роли, summary, tasks, сохранение context;
- быстрый voice-to-input сценарий через микрофон внутри поля ввода;
- `Voice Studio` для локальной озвучки:
  история, выбор голоса, скорость, скачивание, очистка истории;
- `OCR v1` через `+ -> Файл`:
  загрузка изображения, локальное распознавание текста, правка и отправка в чат;
- OCR-пайплайн улучшен для мультиязычных UI-скриншотов (авто-очистка/нормализация извлечённого текста);
- drag-and-drop файлов в chat/ASR и более устойчивое поведение адаптивного UI;
- запуск по локальной сети с телефона через Caddy;
- единое хранение моделей и кэшей только внутри `/models`.

## Последние изменения (по свежим коммитам)

- **2026-04-26** — добавлен ASR pipeline, summary memory, debug endpoints, profile-scoped RAG и UX отсутствующих моделей.
- **2026-04-26** — RAG переведён на отдельные папки профилей, добавлена загрузка файлов из UI и авто-JSON для `.md`.
- **2026-04-22** — улучшен OCR для мультиязычных UI-скриншотов, обновлён drag-and-drop сценарий для чата/ASR.
- **2026-04-22** — переход к `backend/apps/*`, обновление роутов и адаптивного UI.
- **2026-04-20** — упрощён UX `Voice Studio`.
- **2026-04-20** — стабилизация OCR-извлечения для скриншотов, нормализация ссылок/путей и служебных мета-данных.

## Техническая документация

Для инженерного обсуждения архитектуры и планирования развития добавлен отдельный технический документ:

- [`TECHNICAL_README.md`](TECHNICAL_README.md) — память (`mem_turns`), сборка контекста, токены на вход/выход, текущие ограничения и roadmap-пункты.

## Архитектурный принцип

`compare-branch/` сейчас остаётся внутри проекта как `read-only reference`.
Runtime не должен зависеть от кода внутри `compare-branch`: это только база для переноса и сверки решений.

Целевая схема проекта:

- `chat` — диалоги, профили, сообщения, Ollama-модели;
- `asr` — диктовка в input и `ASR Studio`;
- `tts` — `Voice Studio`, Piper-голоса и аудиоистория;
- `ocr` — извлечение текста из изображений;
- `rag` — локальные документы, chunks/embeddings, профильная изоляция;
- `models` — единый корень для всех model-artifacts и кэшей;
- `runtime/LAN` — launcher, Caddy, LAN URL, shutdown-flow.

## Быстрый запуск

Требования:

- Python 3.10+
- Ollama
- ffmpeg
- Tesseract OCR

Основной запуск из корня:

```bash
python3 run_localgpt.py
```

Wrapper-скрипты:

```bash
./start_localgpt.sh
./start_localgpt_lan.sh
```

macOS double-click:

```text
start_localgpt.command
start_localgpt_lan.command
```

Windows:

```text
start_localgpt.bat
```

Legacy alias для LAN-запуска сохранён:

```text
LTrnsrb.command
```

Он остаётся только для backward compatibility и теперь просто вызывает `start_localgpt_lan.sh`.

## Что делает launcher

`run_localgpt.py`:

- создаёт `venv`, если его нет;
- ставит зависимости из `app/requirements.txt`, если они изменились;
- проверяет Ollama;
- поднимает backend;
- открывает локальный UI.

Локальный UI:

```text
http://127.0.0.1:8000/ui/gui_html.html
```

## Запуск с телефона по LAN

Основной LAN entrypoint:

```bash
./start_localgpt_lan.sh
```

или на macOS:

```text
start_localgpt_lan.command
```

Что делает LAN launcher:

- запускает backend в фоне;
- определяет LAN IP;
- поднимает Caddy на HTTPS;
- открывает unified UI по LAN URL;
- пишет runtime-логи во временную директорию пользователя.

Что нужно отдельно:

- `brew install caddy`
- Mac и телефон в одной Wi-Fi сети
- если нужен Safari/iPhone, нужно доверить локальный сертификат Caddy

Полезные LAN файлы:

- `/Users/oleksandrniemchenko/my_personal_files/LocalGPT/tools/LTrnsrb.sh`
- `/Users/oleksandrniemchenko/my_personal_files/LocalGPT/start_localgpt_lan.sh`
- `/Users/oleksandrniemchenko/my_personal_files/LocalGPT/start_localgpt_lan.command`
- `/Users/oleksandrniemchenko/my_personal_files/LocalGPT/Caddyfile.lan`

## UI сценарии

### Чат

- диалоги слева;
- сообщения по центру;
- настройки и модели в отдельной панели;
- меню `+` рядом с полем ввода;
- микрофон внутри поля ввода;
- LAN URL в topbar.

### `+` меню

- `Файл` — OCR v1 для изображений;
- `Транскрибировать` — открывает `ASR Studio`;
- `Озвучить` — открывает `Voice Studio`.

### `ASR Studio`

- отдельная транскрибация аудио/видео;
- история транскриптов;
- редактирование текста;
- действия `Очистить`, `Сделать summary`, `Разобрать по задачам`;
- speaker role editor с ручными overrides;
- пересборка summary с учётом исправленных ролей;
- summary/tasks сохраняются в записи транскрибации и используются для названия записи в истории;
- сохранение processed context в текущий чат;
- удаление записи;
- очистка всей истории;
- вставка processed context в prompt;
- отправка processed context прямо в чат.

Быстрый voice-to-input при этом остаётся отдельным UX и не смешивается с `ASR Studio`.

### `Voice Studio`

- выбор Piper-голоса;
- выбор скорости;
- генерация локального WAV;
- история генераций;
- скачивание записи;
- удаление записи;
- очистка всей истории.

### OCR v1

- принимает изображения;
- локально извлекает текст через Tesseract;
- открывает OCR-редактор;
- позволяет поправить текст;
- позволяет вставить его в prompt или сразу отправить в чат.

### RAG

- кнопка `RAG` в topbar открывает компактную панель документов;
- каждый профиль имеет свою папку `rag_sources/profile_<id>_<name>`;
- новый профиль стартует с пустой RAG-папкой;
- при удалении профиля его RAG-папка удаляется;
- файлы добавляются через `Добавить файлы`;
- после добавления или правки файлов нужно нажать `Индексировать`;
- `Переиндексировать всё` пересобирает chunks/embeddings;
- поддерживаются `.md`, `.json`, `.txt`;
- если рядом с `.md` нет `.json`, LocalGPT создаёт базовый structured JSON;
- если `.json` уже есть, он не перезаписывается и считается source of truth.

Подробная инструкция по подготовке RAG-документов:

- [`rag_sources/README.md`](rag_sources/README.md)

Практическое правило:

- `.md` — объяснение для человека и модели;
- `.json` — точные факты, таблицы, тарифы, SLA, ограничения;
- при конфликте JSON считается правым.

## Пути моделей

Все модели и кэши должны жить только внутри `/models`.

Базовая структура:

```text
models/
├── ollama/
├── whisper/
├── tts/
│   └── piper/
├── hf_cache/
└── ctranslate2_cache/
```

`.env` и `.env.example` поддерживают переносимые относительные пути.

Пример:

```env
MODELS_DIR=models
OLLAMA_MODELS_DIR=models/ollama
WHISPER_MODELS_DIR=models/whisper
TTS_MODELS_DIR=models/tts
PIPER_MODELS_DIR=models/tts/piper
HF_CACHE_DIR=models/hf_cache
CTRANSLATE2_CACHE_DIR=models/ctranslate2_cache

LAN_ACCESS_URL=
LAN_HTTPS_PORT=8443
```

## Ошибки загрузки моделей

Загрузка Ollama-моделей идёт через `/models/pull`.
UI показывает stderr/stdout tail от `ollama pull` и человекочитаемое сообщение.
Список моделей больше не запускает auto-pull: если chat-моделей нет, composer блокируется, а ASR/TTS/OCR остаются доступны.

Для `mistral:7b` важно:

- тег валиден;
- модель может не быть установлена локально;
- исторический сбой мог быть вызван сетевой ошибкой или проблемой доступа к Ollama;
- такие ошибки теперь должны surfaced как человекочитаемое сообщение, а не только `ollama pull вернул код 1`.

## Структура проекта

```text
LocalGPT/
├── app/
│   ├── routes/
│   ├── routers/
│   ├── services/
│   ├── providers/
│   ├── prompts/
│   ├── data/
│   └── db/
├── web_ui/
├── models/
├── rag_sources/
├── compare-branch/          # reference-only, не runtime
│   ├── chat/
│   ├── asr/
│   ├── tts/
│   └── ocr/
├── run_localgpt.py
├── start_localgpt.sh
├── start_localgpt.command
├── start_localgpt_lan.sh
├── start_localgpt_lan.command
├── LTrnsrb.command          # legacy alias
├── tools/LTrnsrb.sh         # LAN launcher implementation
├── .env
└── .env.example
```

## Ключевые файлы

- `/Users/oleksandrniemchenko/my_personal_files/LocalGPT/backend/server.py`
- `/Users/oleksandrniemchenko/my_personal_files/LocalGPT/backend/apps/chat/routes.py`
- `/Users/oleksandrniemchenko/my_personal_files/LocalGPT/backend/apps/chat/service.py`
- `/Users/oleksandrniemchenko/my_personal_files/LocalGPT/backend/apps/asr/pipeline.py`
- `/Users/oleksandrniemchenko/my_personal_files/LocalGPT/backend/apps/rag/service.py`
- `/Users/oleksandrniemchenko/my_personal_files/LocalGPT/backend/apps/rag/routes.py`
- `/Users/oleksandrniemchenko/my_personal_files/LocalGPT/app/routes/transcribe.py`
- `/Users/oleksandrniemchenko/my_personal_files/LocalGPT/app/routes/transcripts.py`
- `/Users/oleksandrniemchenko/my_personal_files/LocalGPT/app/routes/ocr.py`
- `/Users/oleksandrniemchenko/my_personal_files/LocalGPT/app/routers/tts.py`
- `/Users/oleksandrniemchenko/my_personal_files/LocalGPT/app/routes/meta.py`
- `/Users/oleksandrniemchenko/my_personal_files/LocalGPT/app/services/ocr.py`
- `/Users/oleksandrniemchenko/my_personal_files/LocalGPT/app/services/models.py`
- `/Users/oleksandrniemchenko/my_personal_files/LocalGPT/web_ui/gui_html.html`
- `/Users/oleksandrniemchenko/my_personal_files/LocalGPT/web_ui/js/app.js`
- `/Users/oleksandrniemchenko/my_personal_files/LocalGPT/web_ui/css/style.css`

## Диагностика

Health:

```bash
curl -s http://127.0.0.1:8000/health
```

Prompt debug:

```bash
curl -s http://127.0.0.1:8000/chat/debug/prompt
```

Pipeline debug:

```bash
curl -s 'http://127.0.0.1:8000/chat/debug/pipeline?run_id=<id>'
```

Полезные файлы:

- `ollama.log`
- `tmp_logs/chat.log`
- `tmp_logs/pipeline.log`
- runtime-логи launcher в `${TMPDIR}/LocalGPT-<uid>/`

## Текущее ограничение

`compare-branch/` пока не удаляется.
Сейчас внутри него лежат reference-папки `chat / asr / tts / ocr`.
Удаление reference-папок выносится в отдельную cleanup-задачу после полной parity-проверки unified проекта.
