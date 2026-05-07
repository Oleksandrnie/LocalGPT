# LocalGPT

Локальный unified-проект для `chat + ASR + TTS + OCR + LAN + RAG` без внешних облачных API.
Основной runtime работает на `FastAPI + Ollama + faster-whisper + Piper + Tesseract + SQLite`.

## Что уже есть

- `backend/apps/*` mini-app layout для chat/asr/tts/ocr (transitional migration от legacy `app/...`);
- локальный чат с историей, профилями и model settings;
- запуск приложения без загруженной LLM-модели:
  чат показывает состояние отсутствующей модели, а загрузка Ollama-модели выполняется только по явному действию пользователя;
- создание профиля сразу с названием, описанием и необязательным system prompt в настройках;
- очистка SQLite из настроек: мягкая очистка мусора после удалённых чатов и полная очистка БД без удаления локальных моделей;
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
- обновлённый static Web UI:
  collapsible sidebar, toast-уведомления под topbar, единый `AppSelect`, мягкие карточки сообщений, RAG status button, переключатель dark/light theme;
- запуск по локальной сети с телефона через Caddy;
- единое хранение моделей и кэшей только внутри `/models`.

## Последние изменения (по свежим коммитам)

- **2026-05-07** — настройка `Стриминг ответов` поднята в начало вкладки Settings → `Чат / LLM`, новые профили получают `streaming_enabled=true` по умолчанию, а reset возвращает default вместо принудительного выключения.
- **2026-05-06** — завершён verification pass для persistent generation state + SSE: покрыты `stream=true`, `stream=false`, stale-task recovery, missing-model failure, autorouter non-streaming selection и backend/UI smoke-запуск.
- **2026-05-06** — live Ollama SSE smoke подтверждён на локальной `qwen2.5:3b-instruct`; дополнительно усилен Metal-to-CPU retry: перед CPU fallback модель выгружается повторно и для streaming, и для full-response paths.
- **2026-05-06** — настройка `Стриминг ответов` вынесена в заметную Generation-card и теперь сохраняется сразу при переключении, чтобы следующее сообщение не ушло случайно с `stream=false`.
- **2026-05-06** — chat UI восстанавливает активную генерацию при открытии чата после переключения или refresh: находит active assistant-message с `task_id`, переподписывается на SSE/polling и не дублирует уже сохранённый partial content.
- **2026-05-06** — chat UI начал рендерить persistent assistant-message статусы (`generating`, `streaming`, `completed`, `failed`, `cancelled`) и использовать SSE `delta` при включённом стриминге.
- **2026-05-06** — в Settings → `Чат / LLM` добавлен checkbox `Стриминг ответов`; значение хранится в profile preferences как `streaming_enabled` и отправляется в chat generation как `stream`.
- **2026-05-06** — закреплён non-streaming fallback: если `stream` не передан или равен `false`, backend ждёт полный ответ Ollama, не создаёт `delta`, но сохраняет persistent assistant-message lifecycle.
- **2026-05-06** — подключён Ollama streaming для финальной answer-модели: `stream=true` в chat request включает запись partial content в SQLite и передачу `delta` через SSE.
- **2026-05-06** — добавлен backend SSE endpoint `GET /chat/tasks/{task_id}/events` для lifecycle-событий chat generation (`status`, `model_selected`, `done`, `error`, `cancelled`).
- **2026-05-06** — `POST /chat/tasks` подключён к persistent lifecycle: сразу сохраняет user-message и assistant-message `status=generating`, возвращает `user_message_id` / `assistant_message_id`, а завершение task обновляет это assistant-сообщение.
- **2026-05-06** — добавлен storage-слой persistent message lifecycle: `chat_messages` хранит `status`, `model`, `updated_at`, `error`, `task_id`, partial-state и timestamps генерации; старые сообщения мигрируют в `completed`.
- **2026-05-06** — проведён audit текущего chat runtime перед rollout persistent generation state и SSE: активный UI живёт в `web_ui/js/app.js`, чат уже использует `POST /chat/tasks`, но сейчас это polling-only flow без persistent assistant lifecycle.
- **2026-04-28** — старт проекта больше не выбирает fallback LLM и не запускает `ollama pull`; чат блокирует отправку без локальной модели и показывает toast.
- **2026-04-28** — в настройках добавлена очистка БД: удаление осиротевших данных и полный сброс профилей/чатов/RAG-индекса.
- **2026-04-27** — добавлена светлая тема UI с `ThemeToggle`, сохранением в `localStorage`, light tokens и glass-слоями для topbar/sidebar/cards/modals/tools.
- **2026-04-27** — добавлен общий guardrail форматирования расчётов: без LaTeX/MathML/markdown-формул и без запятых как разделителя тысяч в ценах.
- **2026-04-27** — доработан UI v2: floating topbar, collapsible sidebar, toast system, unified `AppSelect`, RAG ON/OFF dot, мягкие message cards и compact composer.
- **2026-04-26** — добавлен ASR pipeline, summary memory, debug endpoints, profile-scoped RAG и UX отсутствующих моделей.
- **2026-04-26** — RAG переведён на отдельные папки профилей, добавлена загрузка файлов из UI и авто-JSON для `.md`.
- **2026-04-26** — настройки профилей разделены на режим редактирования существующего профиля и создание нового профиля.
- **2026-04-22** — улучшен OCR для мультиязычных UI-скриншотов, обновлён drag-and-drop сценарий для чата/ASR.
- **2026-04-22** — переход к `backend/apps/*`, обновление роутов и адаптивного UI.
- **2026-04-20** — упрощён UX `Voice Studio`.
- **2026-04-20** — стабилизация OCR-извлечения для скриншотов, нормализация ссылок/путей и служебных мета-данных.

## Техническая документация

Для инженерного обсуждения архитектуры и планирования развития добавлен отдельный технический документ:

- [`TECHNICAL_README.md`](TECHNICAL_README.md) — память (`mem_turns`), сборка контекста, токены на вход/выход, текущие ограничения и roadmap-пункты.

## Текущий Chat Runtime

Перед внедрением streaming-аудит зафиксировал текущий flow:

- активный chat UI подключён через [`web_ui/gui_html.html`](web_ui/gui_html.html) и [`web_ui/js/app.js`](web_ui/js/app.js); старые модульные файлы `web_ui/js/chat.js`, `web_ui/js/main.js`, `web_ui/js/api.js`, `web_ui/js/sessions.js` не подключены к текущей странице;
- отправка сообщения идёт через `POST /chat/tasks`, а состояние task можно читать через polling `GET /chat/tasks/{task_id}` или lifecycle SSE `GET /chat/tasks/{task_id}/events`;
- storage уже поддерживает persistent statuses `generating`, `streaming`, `completed`, `failed`, `cancelled`, partial content и связь сообщения с `task_id`;
- backend task flow сразу создаёт user-message и assistant-message `status=generating`, возвращает `task_id`, `user_message_id`, `assistant_message_id`, а финализация обновляет тот же assistant-message;
- настройка `Стриминг ответов` живёт первой карточкой в Settings → `Чат / LLM`, сохраняется сразу при переключении в profile preferences как `streaming_enabled` и применяется к следующей отправке; для новых/неинициализированных профилей default — `true`;
- при `stream=true` backend вызывает streaming API Ollama только для финальной answer-модели, пишет partial content в SQLite и отдаёт `delta` через SSE; autorouter остаётся lifecycle/selection этапом без token delta;
- при `stream=false` или отсутствии поля `stream` backend использует full-response fallback без `delta`, но assistant-message всё равно живёт в persistent lifecycle;
- UI рендерит карточки assistant по persistent `status`; `Генерирую ответ...` больше не живёт только в локальном optimistic placeholder;
- при включённом streaming UI подписывается на `GET /chat/tasks/{task_id}/events`, обновляет partial content по `delta`, а при обрыве SSE возвращается к polling;
- при открытии чата UI перечитывает messages, ищет active assistant-message с `task_id` и восстанавливает наблюдение за task; если backend task уже потерян, связанное сообщение переводится в `failed`.

Verification snapshot для этого flow:

- `node --check web_ui/js/app.js`;
- `python -m py_compile` для chat/backend/test файлов;
- `python -m unittest tests.test_pipeline_memory tests.test_model_router -q`;
- smoke-запуск `uvicorn backend.server:app` + `/health` + `/ui/gui_html.html`;
- API-smoke на временной SQLite-базе для `stream=true`, `stream=false`, refresh-state, stale-task и missing-model paths;
- live Ollama smoke на локальной модели с реальными SSE `delta` и финальным persisted assistant-message;
- контроль отсутствия запрещённого AI-флага и realtime-транспорта вне `compare-branch/`.

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
- проверяет и при необходимости запускает Ollama;
- выводит список локальных Ollama-моделей без выбора fallback и без загрузки модели;
- поднимает backend на `8000` или на следующем свободном порту, если `8000` занят;
- открывает локальный UI.

Launcher не делает `ollama pull`, не подставляет `qwen2.5:3b` и не блокирует запуск, если chat-моделей нет. Зависимости, директории и лёгкие health-check операции при первом запуске остаются частью bootstrap.

Локальный UI:

```text
http://127.0.0.1:<фактический-порт>/ui/gui_html.html
```

Фактический URL печатается в терминал как `UI URL`. Если нужен строгий запуск именно на выбранном порту, используйте `--strict-port`.

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

### Профили

- в настройках есть selector профиля с существующими профилями и пунктом `Создать новый профиль`;
- при выборе существующего профиля он становится активным, а в настройках редактируются его описание и system prompt;
- при выборе `Создать новый профиль` поля создания очищаются;
- название нового профиля обязательно, описание и system prompt необязательны;
- после создания новый профиль автоматически становится активным, появляется в левом сайдбаре и остаётся выбранным в настройках.

### Чат

- диалоги слева;
- сообщения по центру;
- настройки и модели в отдельной панели;
- меню `+` рядом с полем ввода;
- микрофон внутри поля ввода;
- LAN URL в topbar;
- правый клик по чату в sidebar открывает контекстное меню для переименования.

### UI / темы

- topbar сделан как floating glass-панель без жёсткого разделителя;
- sidebar можно свернуть/развернуть центральной pill-кнопкой;
- состояние sidebar сохраняется в `localStorage.sidebar_open`;
- горячая клавиша `Cmd+B` на macOS и `Ctrl+B` на Windows/Linux открывает или закрывает sidebar;
- системные статусы показываются toast-уведомлениями под topbar по центру;
- нижняя зона оставлена только под ввод сообщения;
- `RAG` в topbar показывает состояние активного профиля через dot:
  серый OFF, фиолетовый ON;
- `ThemeToggle` в topbar переключает dark/light theme;
- тема сохраняется в `localStorage` через ключ `localgpt_simple_theme`;
- светлая тема использует мягкий фон `#F6F7FB`, radial-пятна, glass-слои, blur и тени;
- кастомный `AppSelect` используется как единый видимый select-компонент.

UI component guide:

- [`docs/ui-components.md`](docs/ui-components.md)

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

### Данные и очистка БД

- удаление профиля полностью удаляет его чаты, сообщения, транскрипты, model settings и RAG-индекс; профильная RAG-папка тоже удаляется;
- удаление отдельного чата удаляет сам chat session и сообщения, а связанные транскрипты/индексные артефакты могут стать осиротевшими `session_id=NULL`;
- кнопка `Очистить мусор` в секции `Whisper модели` удаляет такие осиротевшие chat-данные и запускает `VACUUM`;
- `ASR Studio` история и ручные RAG-файлы `manual_file` мягкой очисткой не удаляются;
- кнопка `Полная очистка` удаляет профили, чаты, сообщения, транскрипты, RAG-индекс и профильные RAG-папки, затем создаёт новый профиль `Default`;
- загруженные LLM/ASR/TTS модели при очистке БД не удаляются.

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
- `Обновить список` перечитывает файлы и статистику без индексации;
- файлы можно удалить из списка кнопкой `×` рядом с названием;
- если галочка RAG включена, backend пытается подмешивать RAG-контекст в каждый chat prompt активного профиля;
- переиндексация нужна только после добавления/изменения файлов, не перед каждым сообщением;
- поддерживаются `.md`, `.json`, `.txt`;
- если рядом с `.md` нет `.json`, LocalGPT создаёт базовый structured JSON;
- ручной `.json` не перезаписывается и считается source of truth;
- авто-JSON с `generated_by: localgpt_auto_structurer` может быть пересобран кнопкой `Индексировать`.

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
├── whisper_cpp/
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
WHISPER_CPP_MODELS_DIR=models/whisper_cpp
TTS_MODELS_DIR=models/tts
PIPER_MODELS_DIR=models/tts/piper
HF_CACHE_DIR=models/hf_cache
CTRANSLATE2_CACHE_DIR=models/ctranslate2_cache

LOCAL_BASE_URL=http://localhost:11434/v1
LOCAL_API_KEY=LOCAL-KEY
LOCAL_MODEL=

LAN_ACCESS_URL=
LAN_HTTPS_PORT=8443
```

## LLM-модели и загрузка

Приложение запускается без LLM-модели. Если локальных Ollama chat-моделей нет, UI показывает состояние `Нет доступных моделей` / `Модель не загружена`.

Поведение без модели:

- поле ввода остаётся активным;
- кнопка отправки недоступна, пока нет выбранной установленной модели;
- сообщение не добавляется в историю;
- backend-запрос к LLM не выполняется;
- при попытке отправки показывается toast: `Нет доступных моделей. Загрузите модель и повторите отправку.`

Загрузка Ollama-модели выполняется только по явному действию пользователя: ввод имени модели, выбор рекомендованной модели или кнопка `Загрузить` в библиотеке LLM. Перед запуском `/models/pull` UI просит подтверждение.

Загрузка Ollama-моделей идёт через `/models/pull`.
UI показывает stderr/stdout tail от `ollama pull` и человекочитаемое сообщение.
Список моделей больше не запускает auto-pull: если chat-моделей нет, composer остаётся доступен для ввода, но отправка отключена; ASR/TTS/OCR остаются доступны.

## ASR и разгрузка CPU на Mac

По умолчанию проект ожидает `whisper.cpp`, чтобы разгружать CPU на Apple Silicon:

```env
WHISPER_BACKEND=whisper_cpp
WHISPER_MODEL_SIZE=large-v3-turbo
WHISPER_CPP_BINARY=models/whisper_cpp/bin/whisper-cli
WHISPER_CPP_MODELS_DIR=models/whisper_cpp
WHISPER_CPP_MODEL_PATH=models/whisper_cpp/ggml-{model}.bin
```

Для этого нужен отдельный `whisper-cli`, собранный с Metal/CoreML, и GGML-модель в `models/whisper_cpp`.

Для macOS есть проектный setup-скрипт:

```bash
tools/setup_whisper_cpp_macos.sh large-v3-turbo
```

Он клонирует `whisper.cpp` в `models/whisper_cpp/source`, собирает `whisper-cli` с Metal/CoreML, создаёт `models/whisper_cpp/bin/whisper-cli` и скачивает `models/whisper_cpp/ggml-large-v3-turbo.bin` вместе с CoreML encoder, если он доступен.
При `WHISPER_BACKEND=whisper_cpp` штатная подготовка ASR-модели (`/whisper/models/prepare`) также скачивает GGML/CoreML файлы в `models/whisper_cpp`, а не faster-whisper snapshot.

Если нужно временно вернуться к старому CPU-based пути:

```env
WHISPER_BACKEND=faster_whisper
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
```

Поведение:

- `whisper_cpp` требует `whisper.cpp` и возвращает понятную ошибку, если binary или модель отсутствуют;
- `auto` использует `whisper.cpp`, только если найден `whisper-cli` и файл модели для выбранного имени (`ggml-large-v3-turbo.bin`, `ggml-medium.bin` и т.п.), иначе переходит на `faster-whisper`;
- `faster_whisper` оставлен как совместимый fallback, но на Mac обычно грузит CPU.

Для `mistral:7b` важно:

- тег валиден;
- модель может не быть установлена локально;
- исторический сбой мог быть вызван сетевой ошибкой или проблемой доступа к Ollama;
- такие ошибки теперь должны surfaced как человекочитаемое сообщение, а не только `ollama pull вернул код 1`.

## Форматирование ответов

Chat runtime добавляет общий system guardrail для оформления расчётов и цен:

- не использовать LaTeX, MathML, markdown-формулы и синтаксис вида `\[...\]`, `\( ... \)`, `\text{...}`;
- не использовать запятую как разделитель тысяч:
  неправильно `35,690 ₽`, правильно `35 690 ₽`;
- суммы выводить обычным человекочитаемым текстом.

Дополнительно `sanitize_reply()` чистит типичный LaTeX-мусор из ответа модели и нормализует записи вроде `23,730 \, \text{₽}` в `23 730 ₽`.

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
- `/Users/oleksandrniemchenko/my_personal_files/LocalGPT/docs/ui-components.md`

## Диагностика

Health:

```bash
curl -s http://127.0.0.1:8000/health
```

Если в UI нет карточки `Стриминг ответов`, сначала проверьте, из какой папки запущен активный backend на том порту, который открыт в браузере:

```bash
lsof -p $(lsof -tiTCP:<port> -sTCP:LISTEN | head -1) | grep cwd
```

Runtime должен быть запущен из текущего checkout LocalGPT; старый процесс из другой копии проекта будет отдавать устаревший `web_ui/gui_html.html`.

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
