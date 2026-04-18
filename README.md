# 🧠 LocalGPT — локальный chat-first ассистент

LocalGPT — полностью локальный ассистент на FastAPI + Ollama + faster-whisper.
Проект работает без внешних облачных API: чат, хранение истории, транскрибация, профили и настройки живут внутри локального проекта.

Текущий интерфейс упрощён до messenger-like сценария:
- диалоги слева;
- сообщения по центру;
- настройки и модели в отдельной панели;
- `+`-меню рядом с полем ввода;
- микрофон внутри поля ввода;
- доступ с телефона по локальной сети через Caddy.

## Что умеет сейчас

- локальный чат через Ollama/OpenAI-compatible endpoint;
- профили и отдельные истории диалогов;
- модельные настройки на уровне профиля и модели:
  `temperature`, `mem_turns`, `max_tokens`, `num_ctx`;
- загрузка и удаление Ollama-моделей из UI;
- транскрибация аудио/видео через faster-whisper;
- голосовой ввод: запись с микрофона, распознавание через Whisper `large-v3-turbo`, вставка текста в поле ввода до отправки;
- локальная озвучка последнего ответа через Piper TTS и кнопку `Озвучить` в меню `+`;
- переносимое хранение путей моделей через `.env`;
- LAN/телефонный запуск через Caddy.

## Быстрый старт

Требования:
- Python 3.10+
- Ollama
- ffmpeg

Запуск из корня проекта:

```bash
python3 run_localgpt.py
```

Быстрые launcher-обёртки из корня:

```bash
./start_localgpt.sh
```

macOS double-click:

```text
start_localgpt.command
```

Windows:

```text
start_localgpt.bat
```

Что делает launcher:
- создаёт `venv`, если его нет;
- ставит зависимости из `app/requirements.txt`, если они изменились;
- проверяет доступность Ollama;
- поднимает backend FastAPI;
- открывает UI в браузере.

Локальный UI:

```text
http://127.0.0.1:8000/ui/gui_html.html
```

Ручной запуск:

```bash
python -m venv venv
source venv/bin/activate
pip install -r app/requirements.txt
ollama serve &
uvicorn app.server:app --host 127.0.0.1 --port 8000
```

## Доступ с телефона через Caddy

Для macOS добавлен отдельный LAN-launcher:

```bash
./LTrnsrb.command
```

или

```bash
./tools/LTrnsrb.sh
```

Что он делает:
- запускает backend в фоне;
- определяет LAN IP;
- поднимает Caddy на `https://<lan-ip>:8443`;
- открывает UI по LAN URL;
- пишет PID и runtime-логи во временную директорию пользователя.

Что нужно отдельно:
- `brew install caddy`
- Mac и телефон в одной Wi-Fi сети
- если нужен доступ из Safari/iPhone, нужно доверить локальный сертификат Caddy

## Текущий UX

Главный сценарий теперь такой:
- открыть существующий чат или создать новый;
- написать сообщение;
- при необходимости:
  - через `+` прикрепить файл на транскрибацию;
  - через микрофон записать голос и превратить его в текст;
  - через `Озвучить` проиграть последний ответ ассистента.

Отдельной плашки `Активный транскрипт` в чате больше нет.
Если транскрипт прикреплён к сессии, это отражается тихо через контекст/логику backend, без лишнего визуального блока.

## Профили, сессии и память

- профили хранятся в SQLite;
- каждая сессия привязана к профилю;
- история сообщений хранится в базе;
- в prompt попадает последние `MEM_TURNS` пар `user/assistant`;
- транскрипт для сессии может быть автоматически подхвачен как контекст;
- model settings хранятся отдельно для пары `profile + model`.

## Транскрибация и голос

### Файловая транскрибация
- загружается аудио/видео;
- backend вызывает `/transcribe`;
- текст сохраняется в SQLite как transcript и становится доступным в контексте сессии.

### Голосовой ввод
- запись идёт в браузере через `MediaRecorder`;
- после остановки запись отправляется на `/transcribe` с `store_result=false`;
- используется Whisper `large-v3-turbo`;
- распознанный текст вставляется в поле ввода;
- история транскриптов при этом не засоряется.

### Озвучка
- кнопка `Озвучить` в меню `+` генерирует локальный WAV через `/tts/generate`;
- используется локальный TTS provider `Piper`;
- выбор TTS provider и голоса вынесен в настройки.

## Модели и пути

Пути управляются через `.env` и могут быть относительными к корню проекта.

Пример:

```env
MODELS_DIR=models
WHISPER_MODELS_DIR=models/whisper
OLLAMA_MODELS_DIR=models/ollama
TTS_MODELS_DIR=models/tts
PIPER_MODELS_DIR=models/tts/piper
HF_CACHE_DIR=models/hf_cache
CTRANSLATE2_CACHE_DIR=models/ctranslate2_cache

LOCAL_BASE_URL=http://localhost:11434/v1
LOCAL_API_KEY=LOCAL-KEY
LOCAL_MODEL=qwen2.5:3b

TEMP=0.25
MAX_TOKENS=512
NUM_CTX=32768
MEM_TURNS=6
```

Что важно:
- относительные пути резолвятся от корня проекта;
- UI умеет менять базовую папку моделей и переносить существующие данные;
- внутри `models/` структура уже разведена по feature-зонам:
  `ollama` для чата, `whisper` для ASR, `tts` для озвучки;
- `.env` сохраняется в переносимом виде, без обязательных абсолютных путей.

## Архитектура по feature-зонам

- `chat`:
  диалоги, профили, сообщения, Ollama-модели и настройки LLM.
- `asr`:
  файловая транскрибация, голосовой ввод и Whisper-модели.
- `tts`:
  локальная озвучка ответов, Piper-голоса и история генераций.

Это разделение сохранено и в коде, и в папках моделей, чтобы дальше можно было отдельно дорабатывать `chat`, `asr` или `tts`.

## Промпты и стили ответов

Системные промпты лежат в:

```text
app/prompts/
```

Ключевые файлы:
- `system_base.md`
- `system_free.md`
- `system_teacher.md`
- `system_business_strict.md`
- `system_explain.md`
- `system_calc.md`
- `system_hr.md`

Важно:
- сейчас основной UI заточен под свободный chat-first режим;
- backend всё ещё поддерживает роли, но UI больше не строится вокруг role-switching в основном потоке;
- prompt-файлы читаются с диска без долгоживущего кэша, поэтому изменения проще тестировать.

## Структура проекта

```text
LocalGPT/
├── app/                  # backend, маршруты, сервисы, промпты, БД-логика
├── web_ui/               # активный chat-first frontend
├── models/               # единое хранилище моделей и кэшей
│   ├── ollama/
│   ├── whisper/
│   ├── tts/
│   ├── hf_cache/
│   └── ctranslate2_cache/
├── app/db/localgpt.db    # SQLite: профили, сессии, сообщения, транскрипты, настройки
├── run_localgpt.py       # основной launcher
├── tools/LTrnsrb.sh      # LAN-launcher для macOS + Caddy
├── LTrnsrb.command       # удобный wrapper для двойного клика
├── .env
└── .env.example
```

## Важные файлы

- `run_localgpt.py` — локальный запуск и bootstrap окружения
- `app/server.py` — FastAPI-приложение
- `app/routes/chat.py` — основной chat endpoint
- `app/routes/transcribe.py` — ASR/transcribe endpoint
- `app/routers/tts.py` — локальный TTS API
- `app/routes/meta.py` — health, roles, runtime shutdown, LAN metadata
- `app/routes/profiles.py` — профили, сессии, model settings
- `web_ui/gui_html.html` — активная HTML-страница
- `web_ui/js/app.js` — активный frontend controller
- `web_ui/css/style.css` — активные стили

## Диагностика

Проверка health:

```bash
curl -s http://127.0.0.1:8000/health
```

Полезные файлы:
- `ollama.log`
- `tmp_logs/chat.log`
- runtime-логи launcher в `${TMPDIR}/LocalGPT-<uid>/`

## Примечания

- Проект остаётся полностью локальным.
- Старые frontend-модули в `web_ui/js/` могут лежать в репозитории как legacy/reference, но активный UI сейчас подключает `web_ui/js/app.js`.
- Если меняете системные промпты или поведение модели, лучше тестировать на новом чате, без старой истории в текущей сессии.
