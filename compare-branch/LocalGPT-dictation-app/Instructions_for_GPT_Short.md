# 🧠 Инструкция (короткая версия)

## Цель
LocalGPT — полностью локальный HR/ASR-бот. Все файлы и модели — внутри `LocalGPT/`.

## Структура
```
LocalGPT/
├── app/            # backend FastAPI, маршруты, промпты ролей
├── web_ui/         # интерфейс (gui_html.html + JS/CSS)
├── models/         # единое хранилище моделей (ollama/, whisper/, hf_cache/, ctranslate2_cache/)
├── run_localgpt.py # запуск + проверки
└── .env            # конфигурация (лежит в репозитории)
```

## Запуск
```
cd LocalGPT
python3 run_localgpt.py
```
Скрипт создаёт venv, ставит зависимости, проверяет Ollama и открывает UI: http://127.0.0.1:8000/ui/gui_html.html.

## Настройки и модели
- Путь к моделям задаётся в `.env` (`MODELS_DIR`, `OLLAMA_MODELS_DIR`, `WHISPER_MODELS_DIR`, `HF_CACHE_DIR`, `CTRANSLATE2_CACHE_DIR`).
- Управлять папкой моделей и переносить кеши можно в настройках UI.
- Пример `.env`:
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

## Роли
- Роли: free, teacher, business_strict, explain, calc, hr.
- Промпты: `app/prompts/system_<role>.md`. Роль выбирается в шапке UI и сохраняется в сессии; для `calc` сначала выполняется безопасный расчёт.

## UI подсказки
- Профили/диалоги слева, сайдбар открывается кнопкой ☰ или Ctrl/Cmd+B (состояние сохраняется).
- Настройки: выбор модели Ollama, загрузки, параметры модели (по профилю), папка моделей, тема.
- Транскрибация: загрузка файла → `/transcribe` → текст и таймлайн сохраняются и применяются к текущей сессии.
- Критерии: CSV/XLSX или Google Sheets через `/criteria/parse`.

## Диагностика
- Health: `curl -s http://127.0.0.1:8000/health`
- Логи: `ollama.log`, `tmp_logs/chat.log`.
