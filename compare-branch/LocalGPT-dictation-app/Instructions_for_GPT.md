# 🧠 LocalGPT — локальный HR/ASR-бот

LocalGPT полностью офлайн: FastAPI + Ollama + faster-whisper, все данные и модели внутри `LocalGPT/`.

---

## ⚙️ Структура проекта
```
LocalGPT/
├── app/                  # backend (FastAPI), маршруты, роли и промпты
├── web_ui/               # интерфейс (HTML/CSS/JS-модули)
├── models/               # единое хранилище моделей/кэшей
│   ├── ollama/           # модели Ollama
│   ├── whisper/          # веса faster-whisper
│   ├── hf_cache/         # кэш Hugging Face
│   └── ctranslate2_cache/# кэш ctranslate2
├── app/db/localgpt.db    # SQLite: профили, сессии, сообщения, транскрипты, настройки моделей
├── run_localgpt.py       # запуск + проверки
├── .env                  # актуальная конфигурация (лежит в git)
└── .env.example          # шаблон переменных
```

---

## 🚀 Запуск
### Базовый
```
python3 run_localgpt.py
```
Скрипт создаёт venv, ставит зависимости, проверяет Ollama, выводит активные пути моделей и открывает UI: `http://127.0.0.1:8000/ui/gui_html.html`.

### Ручной
```
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r app/requirements.txt
ollama serve &
uvicorn app.server:app --host 127.0.0.1 --port 8000
```

---

## 🗂 Модели и .env
Ключевые переменные (см. `.env` и `.env.example`):
```
MODELS_DIR=models
WHISPER_MODELS_DIR=models/whisper
OLLAMA_MODELS_DIR=models/ollama
HF_CACHE_DIR=models/hf_cache
CTRANSLATE2_CACHE_DIR=models/ctranslate2_cache

LOCAL_BASE_URL=http://127.0.0.1:11434/v1
LOCAL_API_KEY=LOCAL-KEY
LOCAL_MODEL=qwen2.5:3b
TEMP=0.2
MAX_TOKENS=2048
NUM_CTX=32768
MEM_TURNS=6
```
- Все веса и кеши лежат в `models/` (можно сменить путь в UI → «Настройки» → «Папка с моделями», с переносом данных).
- Ollama использует `OLLAMA_MODELS_DIR`, faster-whisper — `WHISPER_MODELS_DIR`, Hugging Face/ctranslate2 — свои кэши.
- Легаси каталоги `ollama/` и `ollama_models/` больше не используются по умолчанию — перенесите содержимое в `models/ollama/`.

---

## 🧩 Роли и промпты
- Режимы: `free`, `teacher`, `business_strict`, `explain`, `calc`, `hr`.
- Промпты: `app/prompts/system_<role>.md` (базовый — `system_base.md`, HR — `system_hr.md`).
- Роль хранится в `chat_sessions.role`, выбирается в шапке UI, передаётся в `/chat`.
- Роль `calc` сначала пытается безопасно вычислить арифметическое выражение (+, -, *, /, %, скобки), иначе отвечает кратко через LLM с ограниченным промптом.

---

## 🌐 UI и управление
- Профили/сессии: сайдбар слева; кнопка ☰ в шапке и хоткей Ctrl/Cmd+B открывают/закрывают панель (состояние сохраняется).
- Роль — выпадающий список в шапке (подсказка с описанием).
- Настройки: выбор/скачивание моделей Ollama, параметры модели (по профилю), выбор папки моделей, переключатель темы.
- Транскрибация: загрузка файла → `/transcribe` → текст и таймлайн сохраняются и применяются к текущей сессии. Ручные транскрипты также сохраняются.
- Критерии: CSV/XLSX/Google Sheets через `/criteria/parse` или ручной ввод; сохраняются на сессию.

---

## 📦 Офлайн-подготовка
1. Ollama: скачайте/скопируйте веса в `models/ollama/` (или пропишите свой путь в `.env`).
2. Whisper: скачайте модели Systran faster-whisper в `models/whisper/`.
3. Скопируйте `.env` и папку `models/` на целевую машину — этого достаточно для переноса.

---

## 🔎 Диагностика
- Health: `curl -s http://127.0.0.1:8000/health`
- Логи: `ollama.log`, `tmp_logs/chat.log`.
- БД: `app/db/localgpt.db` (SQLite).

---

## Правила для изменений
- Все файлы — внутри `LocalGPT/`, не трогаем `venv/`.
- Новые файлы кладём в `app/`, `web_ui/` или корень; модели/кэши — в `models/`.
- Не используем внешние API (проект офлайн).
- Роли и промпты редактируем в `app/prompts/`; добавление роли = новый `system_<name>.md` и запись в `app/roles.py`.
