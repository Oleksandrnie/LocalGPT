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
├── app/
│   ├── server.py            # FastAPI-сервер
│   ├── asr_whisper.py       # модуль ASR (Whisper)
│   ├── prompts/
│   │   └── system_hr.md     # системный промпт HR-бота
│   └── __init__.py
├── .env                     # настройки
├── venv/                    # виртуальное окружение Python
└── README.md
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
  WHISPER_MODEL_SIZE=small
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
ENV=local
LOCAL_BASE_URL=http://localhost:11434/v1
LOCAL_API_KEY=LOCAL-KEY
# базовая модель (можно оставить оригинальную)
LOCAL_MODEL=qwen2.5:7b-instruct
# длина ответа по умолчанию (можно поднять до 4096)
MAX_TOKENS=4096
TEMP=0.25

# Локальные модели Whisper (ASR)
WHISPER_MODELS_DIR=./ollama_models/whisper
WHISPER_MODEL_SIZE=medium
WHISPER_COMPUTE_TYPE=int8
WHISPER_DEVICE=cpu
```
> Проект должен быть самодостаточным: все файлы (модели, кэш, Whisper, Ollama long) располагаются внутри папки `LocalGPT/`.

### 3) (Рекомендуется) Собрать long-вариант модели с большим контекстом
Чтобы длинные транскрипты не обрезались по контексту, можно собрать локальную модель с увеличенным `num_ctx`.

```bash
mkdir -p ollama_models/qwen2.5-7b-long
cat > ollama_models/qwen2.5-7b-long/Modelfile <<'EOF'
FROM qwen2.5:7b-instruct
PARAMETER num_ctx 32768
PARAMETER num_predict 4096
PARAMETER temperature 0.25
PARAMETER top_p 0.9
PARAMETER repeat_penalty 1.05
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
