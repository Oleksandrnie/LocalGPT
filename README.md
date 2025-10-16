# Copyright (c) 2025 Oleksandr Niemchenko. All Rights Reserved.
# 🧠 LocalGPT — локальный HR-бот на Mac M1 Pro

Локальный набор:  
- **Ollama** — LLM (Qwen2.5:7B-Instruct)  
- **FastAPI** — REST API `/chat`, `/transcribe`, `/health`  
- **faster-whisper** — транскрибация аудио  
- **Python venv** — изоляция зависимостей  

---

## ⚙️ Структура проекта

```
LocalGPT/
├── .cache/                         # Кэш whisper/ctranslate2
│   └── .gitkeep
│
├── .env                            # Конфигурация окружения
├── .gitattributes
├── .gitignore
│
├── app/                            # Основное FastAPI-приложение
│   ├── __init__.py
│   ├── asr_whisper.py              # Транскрибация (Whisper)
│   ├── requirements.txt            # Зависимости Python
│   ├── server.py                   # Точка входа FastAPI
│   ├── prompts/
│   │   ├── system_hr.md            # Системный промпт
│   │   └── .gitkeep
│   └── .gitkeep
│
├── hf_cache/                       # Hugging Face cache (весов нет, только структура)
│   ├── hub/
│   ├── xet/
│   └── .gitkeep
│
├── ollama_models/                  # Локальные модели Ollama и Whisper
│   ├── id_ed25519
│   ├── id_ed25519.pub
│   ├── models/
│   │   ├── blobs/
│   │   └── manifests/registry.ollama.ai/library/qwen2.5-7b-instruct
│   ├── qwen2.5-7b-long/
│   │   ├── Modelfile
│   │   └── .gitkeep
│   └── whisper/
│       ├── medium/
│       │   ├── models--Systran--faster-whisper-medium/
│       │   │   ├── blobs/
│       │   │   ├── refs/
│       │   │   └── snapshots/
│       │   └── .gitkeep
│       └── .gitkeep
│
├── venv/                           # Виртуальное окружение Python
│   ├── bin/
│   ├── lib/
│   ├── include/
│   ├── share/
│   ├── pyvenv.cfg
│   └── .gitkeep
│
├── web_ui/                         # Веб-интерфейс
│   ├── gui_html.html
│   ├── style.css
│   └── .gitkeep
│
├── first_run.py                    # Автоматическая установка и настройка
├── Instructions_for_GPT.md         # Инструкция для LLM
├── License                         # Лицензия проекта
├── README.md                       # Этот файл
└── run_localgpt.sh                 # Скрипт запуска
```

---

## 🚀 Первый запуск

```bash
# 1. Перейди в папку проекта
cd ./LocalGPT

# 2. Активируй виртуальное окружение
source venv/bin/activate

# 3. Убедись, что Ollama запущен
brew services start ollama
# (или в отдельном окне)
ollama serve &

# 4. Убедись, что модель скачана
ollama pull qwen2.5:7b-instruct

# 5. Запуск FastAPI
export PYTHONPATH="$(pwd)"
uvicorn app.server:app --host 127.0.0.1 --port 8000 --log-level info
```

---

## 🧪 Проверка API

### 1. Статус
```bash
curl http://127.0.0.1:8000/health
```

### 2. Чат
```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query":"Сформируй 3 вопроса для скрининга Middle Python"}'
```

### 3. Транскрибация (ASR)
```bash
curl -X POST http://127.0.0.1:8000/transcribe \
  -F "file=@sample.wav" \
  -F "language=ru"
```

---

## 🔁 Перезапуск сервера

Если внёс изменения в `server.py` или `.env`:
```bash
# Останови сервер
Ctrl + C

# Перезапусти
source venv/bin/activate
export PYTHONPATH="$(pwd)"
uvicorn app.server:app --host 127.0.0.1 --port 8000 --log-level info
```

---

## 🧹 Полезные команды

| Цель | Команда |
|------|----------|
| Список моделей Ollama | `curl -s http://127.0.0.1:11434/v1/models` |
| Скачать модель | `ollama pull qwen2.5:7b-instruct` |
| Перезапустить Ollama | `brew services restart ollama` |
| Проверить FastAPI | `curl http://127.0.0.1:8000/health` |
| Установить зависимости | `pip install -r ./app/requirements.txt` |
| Добавить пакет | `pip install <имя_пакета>` |
| Проверить Python-модуль | `python -m app.server` |
| Проверить Whisper | `python -m app.asr_whisper` |

---

## 🧩 Важно знать

- Ответы модели теперь **только на русском языке** — добавлено системное правило.  
- Если модель отвечает странно или частично на китайском/английском — перезапусти сервер.  
- Для быстрой работы ASR можно в `.env` заменить:
  ```
  WHISPER_MODEL_SIZE=medium
  ```

---

## 🧰 Частые проблемы

| Ошибка | Решение |
|--------|----------|
| `ModuleNotFoundError: No module named 'asr_whisper'` | Добавь `__init__.py` в `app/` |
| `Form data requires "python-multipart"` | `pip install python-multipart` |
| Ollama: `server not responding` | Перезапусти: `brew services restart ollama` |
| Ответ модели на другом языке | Перезапусти сервер — у тебя уже встроено правило "только русский" |

---

## ✅ Готово

После запуска можешь отправлять запросы к `/chat` из любой системы, поддерживающей OpenAI API-формат — Postman, cURL, Python, Node.js и т.д.

---


Автор: 🧑‍💻 Oleksandr Niemchenko  
Версия проекта: 1.0 (локальная, Mac M1 Pro)

## 🌍 Развёртывание на другом ПК / сервере (из Git)

Ниже — пошаговая инструкция, чтобы поднять проект **с нуля на чистой машине** (macOS или Linux) после `git clone`.

### 0) Предустановки
- **Python 3.10+** (рекомендация)
- **pip** и **venv**
- **Git**
- **Ollama** (LLM-сервер)
- (Опционально) **Homebrew** на macOS

**Установка Ollama:**
- macOS: `brew install ollama && brew services start ollama`
- Linux: 
  ```bash
  curl -fsSL https://ollama.com/install.sh | sh
  sudo systemctl enable --now ollama
  ```

### 1) Клонирование и базовая подготовка
```bash
# всё разворачивается в текущей директории
mkdir -p my_personal_files
cd my_personal_files

git clone <URL_ВАШЕГО_РЕПО> LocalGPT
cd ./LocalGPT

# создаём и активируем venv
python3 -m venv venv
source venv/bin/activate

# ставим зависимости бэкенда
pip install -r ./app/requirements.txt
```

### 2) Конфигурация `.env`
Создай файл `.env` (или скопируй из репозитория, если он есть) и проверь ключевые переменные:
```env
# Copyright (c) 2025 Oleksandr Niemchenko. All Rights Reserved.
ENV=local

# OpenAI-совместимый эндпоинт Ollama
LOCAL_BASE_URL=http://localhost:11434/v1
LOCAL_API_KEY=LOCAL-KEY

# Модель по умолчанию
# Если уже собрал long-модель — оставь строку ниже как есть.
# Если ещё нет — временно поставь qwen2.5:7b-instruct.
LOCAL_MODEL=qwen2.5-7b-long

# Параметры генерации
TEMP=0.2
MAX_TOKENS=1200
MEM_TURNS=6  
# MEM_TURNS=6  сколько пар (user+assistant) хранить в памяти на сессию

# Whisper (ASR)
WHISPER_MODEL_SIZE=medium   # варианты: tiny/base/small/medium/large-v3
WHISPER_COMPUTE_TYPE=int8   # экономный режим на Mac

# для перезапуска модели через web ui
ADMIN_TOKEN=local-admin-123

# локальные модели Whisper
WHISPER_MODELS_DIR=./ollama_models/whisper
WHISPER_DEVICE=cpu
```
> Проект должен быть самодостаточным: все файлы (модели, кэш, Whisper, Ollama long) располагаются внутри папки `LocalGPT/`.

### 3) (Рекомендуется) Собрать long-вариант модели с большим контекстом
Чтобы длинные транскрипты не обрезались по контексту, можно собрать локальную модель с увеличенным `num_ctx`.

```bash
mkdir -p ollama_models/qwen2.5-7b-long
cat > ollama_models/qwen2.5-7b-long/Modelfile <<'EOF'
FROM qwen2.5:7b-instruct

# Контекст/вывод
PARAMETER num_ctx 32768
PARAMETER num_predict 1024   
# PARAMETER num_predict 1024    было 4096 — слишком длинно → провоцирует «залипание»

# Стабильная генерация
PARAMETER temperature 0.2
PARAMETER top_p 0.9
PARAMETER repeat_penalty 1.2
PARAMETER repeat_last_n 1024

# Mirostat — сильно уменьшает повторы/утечки
PARAMETER mirostat 2
PARAMETER mirostat_tau 5.0
PARAMETER mirostat_eta 0.1

# Шаблон
TEMPLATE """{{ .System }}
{{ .Prompt }}"""
EOF

# сборка модели
cd ollama_models/qwen2.5-7b-long
ollama create qwen2.5-7b-long -f Modelfile
ollama list   # убедись, что модель появилась
cd ../../

# переключаем сервер на новую модель
# (или сделай это в .env)
sed -i '' 's/^LOCAL_MODEL=.*/LOCAL_MODEL=qwen2.5-7b-long/' .env 2>/dev/null || \
  sed -i 's/^LOCAL_MODEL=.*/LOCAL_MODEL=qwen2.5-7b-long/' .env || true
```
> Если памяти мало — поставь `PARAMETER num_ctx 16384`.

### 4) Подготовка ASR-моделей Whisper (без скачивания с нуля)
Вариант A — **скопировать** уже скачанные модели в проект:
```bash
# пример для medium (Systran faster-whisper)
mkdir -p ollama_models/whisper/medium
cp -R ~/.cache/huggingface/hub/models--Systran--faster-whisper-medium \
      ollama_models/whisper/medium/
```
Структура может быть такой:
```
ollama_models/whisper/medium/models--Systran--faster-whisper-medium/snapshots/<rev>/{model.bin,config.json,...}
```
Наш `asr_whisper.py` **сам найдёт** корректную папку `snapshots/<rev>` по `WHISPER_MODELS_DIR`.

Вариант B — оставить скачивание в первый запуск: просто убедись, что `.env` содержит `WHISPER_MODEL_SIZE`, и при первом вызове `/transcribe` модели подтянутся в кэш.

### 5) Запуск
```bash
# убедись, что Ollama запущен
ollama serve &   # macOS: brew services start ollama

# запусти API
export PYTHONPATH="$(pwd)"
uvicorn app.server:app --host 127.0.0.1 --port 8000 --log-level info
```
Открой UI: http://127.0.0.1:8000/

### 6) Быстрые проверки
```bash
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/version
curl -s http://127.0.0.1:11434/v1/models
```

### 7) Типичные проблемы и решения
| Проблема | Причина | Решение |
|---|---|---|
| `Error: connection refused` к Ollama | служба не запущена | macOS: `brew services start ollama`; Linux: `systemctl start ollama` |
| Ответы модели обрываются | малый `num_ctx` или `MAX_TOKENS` | собери long-модель (см. п.3) и/или подними `MAX_TOKENS` в `.env` |
| `Form data requires python-multipart` | пакет не установлен | `pip install python-multipart` |
| ASR заново качает веса | не задан `WHISPER_MODELS_DIR` | пропиши путь в `.env` или скопируй модели в `ollama_models/whisper` |
| UI не открывается | сервер не запущен / CORS | проверь логи `uvicorn`, порт `8000`, CORS включён в `server.py` |

---

## 📌 Памятка по продакшн/серверу
- Запуск под `systemd`/pm2/supervisor (для uvicorn) — чтобы сервисы автоматически стартовали.
- Резервное копирование `.env` и папки `ollama_models/`.
- На ARM/Linux проверь compute type и память. Для CPU: int8 чаще всего оптимален.

```bash
# посмотреть параметры собранной модели
ollama show qwen2.5-7b-long | grep -i -E 'num_ctx|num_predict|temperature|top_p|repeat'
```
