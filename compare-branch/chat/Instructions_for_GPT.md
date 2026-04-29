# 🧠 LocalGPT — актуальная техническая памятка

Этот файл описывает текущее состояние проекта в ветке, без старых промежуточных UI-версий.

## 1. Что это за проект

LocalGPT — локальный chat-first ассистент:
- FastAPI backend;
- Ollama/OpenAI-compatible LLM endpoint;
- faster-whisper для ASR;
- SQLite для профилей, сессий, сообщений, транскриптов и model settings;
- LAN-доступ через Caddy launcher на macOS.

Основной сценарий больше не HR-first.
Сейчас это обычный локальный чат, в котором HR-режим остался только как backend-capability, а не как визуальный центр продукта.

## 2. Активные entrypoints

### Backend
- `app/server.py`
- `run_localgpt.py`

### Frontend
Активный frontend подключён так:
- HTML: `web_ui/gui_html.html`
- JS: `web_ui/js/app.js`
- CSS: `web_ui/css/style.css`

Важно:
- в `web_ui/js/` остались legacy-модули (`main.js`, `models.js`, `sessions.js` и т.д.);
- текущая страница использует именно `app.js`.

## 3. Текущий UI

Текущий интерфейс:
- фиксированный список чатов слева;
- поток сообщений по центру;
- панель настроек как боковая модалка;
- `+`-меню у поля ввода;
- микрофон внутри поля ввода;
- `Отправить` disabled, если textarea пустая;
- отдельный блок `Активный транскрипт` из chat area убран.

Что доступно в настройках:
- выбор LLM-модели;
- скачивание/удаление моделей Ollama;
- профиль и управление профилями;
- model settings:
  - `temperature`
  - `mem_turns`
  - `max_tokens`
  - `num_ctx`
- Whisper settings;
- пути моделей;
- LAN URL и runtime shutdown;
- список активных загрузок моделей.

## 4. Голос и транскрибация

### Файловая транскрибация
- выполняется через `/transcribe`;
- результат сохраняется в SQLite и может стать контекстом чата.

### Voice input
- запись идёт через `MediaRecorder` в браузере;
- после записи blob идёт на `/transcribe` с `store_result=false`;
- используется Whisper `large-v3-turbo`;
- текст вставляется в поле ввода;
- этот сценарий не создаёт постоянную запись transcript в истории.

### Озвучка
- не локальная TTS-модель;
- используется `window.speechSynthesis` в браузере.

## 5. Память и контекст

Контекст запроса собирается в `/chat` так:
1. system prompt = base + role
2. явный `context`, если он передан
3. transcript из запроса или последний transcript для сессии
4. criteria из запроса или сохранённые для сессии
5. последние `MEM_TURNS` пар истории
6. текущий запрос пользователя

Реально visible role-switching в основном UI сейчас убран, но backend-механизм ролей сохранён.

## 6. Prompt layer

Prompt-файлы:
- `app/prompts/system_base.md`
- `app/prompts/system_free.md`
- `app/prompts/system_teacher.md`
- `app/prompts/system_business_strict.md`
- `app/prompts/system_explain.md`
- `app/prompts/system_calc.md`
- `app/prompts/system_hr.md`

Важно:
- prompt-файлы читаются с диска без долгоживущего `lru_cache`;
- изменения проще тестировать без полной пересборки логики;
- для проверки качества ответов лучше использовать новый чат, без старой истории.

## 7. Модели и пути

Проект опирается на portable paths:
- `MODELS_DIR`
- `WHISPER_MODELS_DIR`
- `OLLAMA_MODELS_DIR`
- `HF_CACHE_DIR`
- `CTRANSLATE2_CACHE_DIR`

Относительные пути резолвятся от корня проекта.
`.env` сохраняется в переносимом виде, чтобы проект можно было переносить между машинами без жёсткой привязки к абсолютным путям.

## 8. LAN launcher

LAN launcher:
- `tools/LTrnsrb.sh`
- `LTrnsrb.command`

Сценарий:
- старт backend в фоне;
- генерация Caddy config;
- reverse proxy на `https://<lan-ip>:8443`;
- логирование PID/runtime state в `${TMPDIR}/LocalGPT-<uid>`.

## 9. Что важно не перепутать

- Активный UI больше не `main.js`, а `app.js`.
- Проект больше не должен документироваться как “локальный HR/ASR-бот” в главном описании.
- Browser TTS и local ASR — это разные сценарии.
- Не стоит возвращать в основной UI отдельные большие блоки для transcript/HR/role, если это не требуется явно.
- Для длинных/обрывающихся ответов важен backend-вызов LLM, а не только prompt.
