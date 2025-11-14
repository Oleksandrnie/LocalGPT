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

В каталоге `ollama_models/qwen2.5-7b-long/Modelfile` хранится Modelfile — параметры локальной LLM (`NUM_CTX`, `MAX_TOKENS`, `TEMP` и др.).

---

## 📝 Кастомизация системного промпта

Базовый HR-промпт лежит в `app/prompts/system_hr.md`. Измените этот файл, чтобы адаптировать тон, формат и правила ответов под ваши процессы.

> ⚠️ Файл читается в кодировке UTF-8. Если промпт окажется повреждённым или его нельзя декодировать, backend залогирует предупреждение и автоматически использует встроенный резервный промпт, чтобы API продолжило отвечать. После правок перезапустите сервис, чтобы загрузить обновлённый текст.

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

Скрипт `run_localgpt.py` ведёт пошаговый лог в stdout. Он показывает, какой шаг выполняется:
- путь до проекта и используемый venv;
- создание виртуального окружения (если его нет);
- установку зависимостей из `app/requirements.txt`;
- проверку запуска Ollama и старт `ollama serve` при необходимости;
- проверку наличия модели `qwen2.5:7b-instruct` (`ollama pull` при первом запуске);
- чтение `.env`, проверку модели `LOCAL_MODEL` через `ollama show` и автоматический фолбэк (создание по Modelfile или переключение на доступную модель);
- открытие UI по адресу `http://127.0.0.1:8000/`;
- запуск FastAPI через `uvicorn app.server:app`.

По этим сообщениям можно быстро понять, где запуск остановился.

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

## 🧾 Примеры `.env`

**Стандартная (короткий контекст) конфигурация:**
```env
LOCAL_MODEL=qwen2.5:7b-instruct
LOCAL_BASE_URL=http://127.0.0.1:11434/v1
LOCAL_API_KEY=LOCAL-KEY
TEMP=0.25
MAX_TOKENS=512
NUM_CTX=32768
MEM_TURNS=6
WHISPER_MODEL_SIZE=medium
WHISPER_COMPUTE_TYPE=int8
WHISPER_DEVICE=cpu
ADMIN_TOKEN=local-admin-123
```

**Long-контекст (`qwen2.5-7b-long`):**
```env
LOCAL_MODEL=qwen2.5-7b-long
LOCAL_BASE_URL=http://127.0.0.1:11434/v1
LOCAL_API_KEY=LOCAL-KEY
TEMP=0.2
MAX_TOKENS=2048
NUM_CTX=65536
MEM_TURNS=8
WHISPER_MODEL_SIZE=medium
WHISPER_COMPUTE_TYPE=int8
WHISPER_DEVICE=cpu
ADMIN_TOKEN=local-admin-123
```

Если Ollama или OpenAI-совместимый API работает на другой машине, укажите её адрес и ключ в `LOCAL_BASE_URL` и `LOCAL_API_KEY`.

---

## 🗣 Транскрибация (Whisper)

В UI теперь доступны:
- выбор Whisper‑модели (`small` — быстрее, `medium` — качественнее),
- выбор пресета промпта: `none`, `ru`, `en`.

Backend использует `transcribe_with_fallback` и делает два прохода:
1. **Первый проход:** автоопределение языка (language=`auto`) + VAD + промпт (preset + `whisper_prompt.txt`).
2. **Фолбэк:** VAD отключён, язык берётся из запроса (`language` в `/transcribe`) либо из `WHISPER_FALLBACK_LANGUAGE`, промпт сохраняется, если не отключён переменной `WHISPER_FALLBACK_USE_PROMPT`.

Поле `language` принимает `auto` (значение по умолчанию) или BCP‑47 код (`ru`, `en`, `pt-br` и т.д.). Некорректные значения отклоняются с ошибкой 422.

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

Для настройки фолбэка доступны дополнительные переменные окружения:
```
WHISPER_FALLBACK_LANGUAGE=ru            # язык второго прогона, если клиент не прислал свой
WHISPER_FALLBACK_USE_PROMPT=true        # использовать тот же initial_prompt во втором проходе
```

---

## 📥 Как загружаются модели

**LLM (Qwen 2.5):**
- При запуске `run_localgpt.py` читается `LOCAL_MODEL` из `.env`, выполняется `ollama show <model>` и, при необходимости, запускается автоматическая подготовка (создание по Modelfile либо переключение `.env` на существующую модель).
- Если модель из `.env` недоступна, лаунчер пытается подтянуть fallback `qwen2.5:7b-instruct` (`ollama pull`) или выбрать любую другую установленную модель.
- Кастомный вариант `qwen2.5-7b-long` собирается по Modelfile `ollama_models/qwen2.5-7b-long/Modelfile` командой:
  ```bash
  ollama create qwen2.5-7b-long -f ollama_models/qwen2.5-7b-long/Modelfile
  ```

**Whisper (ASR):**
- При первом запуске транскрибации с выбранной моделью (`small` или `medium`) `faster-whisper` скачивает веса из Hugging Face (если есть интернет) и сохраняет их в каталог `LocalGPT/ollama_models/whisper/` (или в путь из `WHISPER_MODELS_DIR`).
- При отсутствии интернета модели Whisper можно заранее скачать на другой машине и скопировать в этот каталог вручную — после этого транскрибация будет работать офлайн.

---

### 🔍 Диагностика long-модели

1. Посмотрите, установлена ли модель, командой `ollama list`. В списке должна появиться строка `qwen2.5-7b-long` с ожидаемым размером.
2. Проверьте, что Ollama может её загрузить: `ollama show qwen2.5-7b-long`. Успешный вывод означает, что модель доступна для инференса.
3. Убедитесь в размере контекста: `ollama show qwen2.5-7b-long --config | grep context`. Для long-сборки ожидается `"context_length": 65536`.
4. Если модель отсутствует, соберите её заново по Modelfile: `ollama create qwen2.5-7b-long -f ollama_models/qwen2.5-7b-long/Modelfile`.

---

## 📦 Подготовка к офлайн-режиму

1. **LLM (Ollama):**
   - На машине с интернетом выполните `ollama pull qwen2.5:7b-instruct` (и при необходимости `ollama create qwen2.5-7b-long -f ollama_models/qwen2.5-7b-long/Modelfile`).
   - Скопируйте каталог `~/.ollama/models` на офлайн-машину (в тот же путь) или в `LocalGPT/ollama_models/` внутри проекта.
   - Убедитесь, что на офлайн-машине запущен `ollama serve`, а `LOCAL_MODEL` в `.env` указывает на нужную локальную модель.
2. **Whisper:**
   - Скачайте архивы весов (`small`, `medium` и т.д.) из репозиториев `Systran/faster-whisper-*` на Hugging Face.
   - Распакуйте их в `LocalGPT/ollama_models/whisper/<model-name>` или в директорию, указанную `WHISPER_MODELS_DIR`.
3. **Конфигурация и зависимости:**
   - В `.env` выставьте локальные `LOCAL_BASE_URL` и `LOCAL_API_KEY` (по умолчанию `http://127.0.0.1:11434/v1` и `LOCAL-KEY`).
   - При полном отсутствии интернета заранее соберите виртуальное окружение (запустите `run_localgpt.py` на машине с доступом в сеть или сохраните wheel-файлы зависимостей).

---

## 📌 Примечание
Все модели, кэш и конфигурации хранятся **внутри проекта**.
