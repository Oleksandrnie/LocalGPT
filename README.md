# 🧠 LocalGPT — локальный HR‑ и ASR‑бот

LocalGPT — полностью локальный HR‑бот и помощник для транскрибации, работающий **без интернета** и **без внешних API**. 
Поддерживает чат, анализ текста, транскрибацию аудио/видео и работу с локальными LLM через Ollama.

---

## ⚙️ Структура проекта
```
LocalGPT/
├── app/                # FastAPI backend
├── web_ui/             # Лёгкий веб‑интерфейс
├── ollama_models/      # Локальные модели (LLM + Whisper)
├── venv/               # Виртуальное окружение Python
├── run_localgpt.py     # Универсальный запуск (macOS / Linux / Windows)
└── .env                # Конфигурация
```

В каталоге `ollama_models/qwen2.5-7b-long/Modelfile` хранится Modelfile — параметры локальной LLM (контекст, длина ответа, температура и др.).

---

## 🚀 Запуск

### macOS / Linux
```
git clone <URL> LocalGPT
cd LocalGPT
python3 run_localgpt.py
```

### Windows
```
powershell
git clone <URL> LocalGPT
cd LocalGPT
py run_localgpt.py
```

Скрипт `run_localgpt.py` автоматически:
- создаёт виртуальное окружение;
- ставит зависимости;
- запускает Ollama;
- скачивает модель `qwen2.5:7b-instruct`, если её нет;
- поднимает API по адресу `http://127.0.0.1:8000/`;
- открывает UI.

---

## 🔧 Ручной запуск (альтернатива)
```
python -m venv venv
source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r app/requirements.txt
ollama serve &               # Windows: ollama serve
ollama pull qwen2.5:7b-instruct
export PYTHONPATH="$(pwd)"  # Windows: set PYTHONPATH=%cd%
uvicorn app.server:app --host 127.0.0.1 --port 8000
```

---

## 🗣 Транскрибация (Whisper)

В UI теперь доступны:
- выбор Whisper‑модели (`small` — быстрее, `medium` — качественнее),
- выбор пресета промпта: `none`, `ru`, `en`.

Backend использует `transcribe_with_fallback`:
1. **Первый проход:** auto‑language + VAD + промпт (preset + `whisper_prompt.txt`).
2. **Фолбэк:** language=`ru`, без VAD и без промпта.

Файл `whisper_prompt.txt`, лежащий рядом с аудиофайлом, автоматически подмешивается в промпт.

Whisper‑модели хранятся внутри проекта по пути:
```
LocalGPT/ollama_models/whisper/
```
При первом использовании выбранной модели она будет загружена (если доступен интернет) и сохранена в этот каталог.  
Путь можно переопределить переменной в `.env`:
```
WHISPER_MODELS_DIR=ollama_models/whisper
```

---

## 📥 Как загружаются модели

**LLM (Qwen 2.5):**
- При запуске `run_localgpt.py` проверяется наличие базовой модели `qwen2.5:7b-instruct` в Ollama.
- Если её нет, лаунчер выполняет `ollama pull qwen2.5:7b-instruct` и скачивает модель один раз.
- Кастомный вариант `qwen2.5-7b-long` собирается по Modelfile в `ollama_models/qwen2.5-7b-long/Modelfile` командой:
  ```bash
  ollama create qwen2.5-7b-long -f ollama_models/qwen2.5-7b-long/Modelfile
  ```

**Whisper (ASR):**
- При первом запуске транскрибации с выбранной моделью (`small` или `medium`) `faster-whisper` скачивает веса из Hugging Face (если есть интернет) и сохраняет их в каталог `LocalGPT/ollama_models/whisper/` (или в путь из `WHISPER_MODELS_DIR`).
- При отсутствии интернета модели Whisper можно заранее скачать на другой машине и скопировать в этот каталог вручную — после этого транскрибация будет работать офлайн.

---

## 📌 Примечание
Все модели, кэш и конфигурации хранятся **внутри проекта**.
