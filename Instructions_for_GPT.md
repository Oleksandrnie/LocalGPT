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

Скрипт `run_localgpt.py` ведёт пошаговый лог в stdout и показывает, какой шаг выполняется:
- путь до проекта и используемый venv;
- создание виртуального окружения (если его нет);
- установка зависимостей из `app/requirements.txt`;
- проверка запуска Ollama и старт `ollama serve` при необходимости;
- проверка наличия модели `qwen2.5:3b` (минимальная; если моделей нет, автоскачка при первом запуске);
- попытка открыть UI по адресу `http://127.0.0.1:8000/`;
- запуск FastAPI через `uvicorn app.server:app`.

---

## 🔧 Ручной запуск (альтернатива)
```
python -m venv venv
source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r app/requirements.txt
ollama serve &               # Windows: ollama serve
ollama pull qwen2.5:3b
export PYTHONPATH="$(pwd)"  # Windows: set PYTHONPATH=%cd%
uvicorn app.server:app --host 127.0.0.1 --port 8000
```

---

## 🧾 Примеры `.env`

**Стандартная (короткий контекст, минимальная) конфигурация:**
```env
LOCAL_MODEL=qwen2.5:3b
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

**Long-контекст (`qwen2.5-7b-long`) по желанию:**
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

Backend использует `transcribe_with_fallback`:
1. **Первый проход:** auto‑language + VAD + промпт (preset + `whisper_prompt.txt`).
2. **Фолбэк:** language=`ru`, без VAD и без промпта.

Файл `whisper_prompt.txt`, лежащий рядом с аудиофайлом, автоматически подмешивается в промпт.

Whisper‑модели хранятся внутри проекта по пути:
```
LocalGPT/ollama_models/whisper/
```
При первом использовании выбранной модели она будет загружена (если доступен интернет) и помещена в этот каталог.
Путь можно изменить в `.env` с помощью переменной:
```
WHISPER_MODELS_DIR=ollama_models/whisper
```

---

## 📦 Подготовка к офлайн-режиму

1. **LLM (Ollama):**
   - На машине с интернетом выполните `ollama pull qwen2.5:3b` (и при необходимости `ollama create qwen2.5-7b-long -f ollama_models/qwen2.5-7b-long/Modelfile`).
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
# 📘 INSTRUCTIONS_FOR_GPT.md
_Инструкция для ChatGPT (или другого LLM-помощника), работающего с проектом LocalGPT._

---

## 🎯 Цель
Проект **LocalGPT** — полностью локальный HR‑ и ASR‑бот. Всё должно находиться в директории проекта `LocalGPT/`.

---

## 🧱 Структура проекта
```
LocalGPT/
├── .env
├── INSTRUCTIONS_FOR_GPT.md
├── Instructions_for_GPT_Short.md
├── Instructions_for_GPT_Context.md
├── README.md
├── run_localgpt.py
│
├── app/
│   ├── server.py
│   ├── asr_whisper.py
│   ├── prompts/system_hr.md
│   └── requirements.txt
│
├── web_ui/
│   └── gui_html.html
│
├── ollama_models/
│   ├── models/                 # каталог для скачанных моделей Ollama (пустой по умолчанию, .gitkeep)
│   └── qwen2.5-7b-long/Modelfile
│       - Настройки модели: NUM_CTX, MAX_TOKENS, TEMP, mirostat…
│
├── hf_cache/
└── .cache/ctranslate2/
```

---

## 🧩 Основные компоненты
| Компонент | Назначение |
|----------|------------|
| FastAPI | `/chat`, `/transcribe`, `/health`, `/version` |
| Ollama | Локальный LLM‑сервис |
| faster-whisper | Транскрибация |
| asr_whisper.py | Логика fallback‑транскрибации |
| web_ui | GUI |
| История транскрибаций | Компактный список, действия: использовать / редактировать / удалить |
| ollama_models/models | Путь для скачанных LLM; по умолчанию пуст, автосоздаётся и игнорируется в git |
| .env | Конфигурация |
| run_localgpt.py | Единый запуск |

---

## ⚙️ Правила
- Все файлы только внутри `LocalGPT/`.
- Редактировать существующие файлы, новые — класть в `app/`, `web_ui/` или корень.
- Не трогать `venv/`.
- Пути только относительные.
- Зависимости в `app/requirements.txt`.
- История транскрибаций: клики по карточке → кнопки использовать/редактировать/удалить. Кнопка редактировать открывает модалку по центру с чтением/переименованием/применением/удалением выбранного транскрипта.
- Модели Ollama качаются в `ollama_models/models/` (env `OLLAMA_MODELS_DIR`/`OLLAMA_MODELS`). Каталог пустой по умолчанию, в git только `.gitkeep`/`Modelfile`. При первом запуске, если моделей нет, автозапускается загрузка минимальной модели (`qwen2.5:3b` по умолчанию). Загрузку можно остановить через API `/models/pull/{task_id}/cancel`; удаление доступно только для уже скачанных моделей.

---

## 🚀 Запуск
```
cd /путь/к/LocalGPT
python3 run_localgpt.py
```
UI → `http://127.0.0.1:8000/`

---

## 🗣 ASR / Whisper

Функция `transcribe_with_fallback`:
1. auto‑language + VAD + initial_prompt (preset + `whisper_prompt.txt`)
2. fallback: ru, без VAD, без промпта.

Эндпоинт `/transcribe` принимает:
- `file` — аудио,
- `model` — tiny/base/small/medium/large,
- `prompt_preset` — none/ru/en.

UI содержит два селекта: **модель** и **preset**.

---

## 🧰 Диагностика
| Что | Команда |
|-----|---------|
| Ollama работает? | `curl -s http://127.0.0.1:11434/v1/models` |
| API жив? | `curl -s http://127.0.0.1:8000/health` |
| Версия | `curl -s http://127.0.0.1:8000/version` |

---

## 🔧 Настройка модели (Modelfile)
После обновления Modelfile →
```
ollama create qwen2.5-7b-long -f ollama_models/qwen2.5-7b-long/Modelfile
```

---

## 📄 .env
```env
LOCAL_MODEL=qwen2.5:3b
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

Для стандартной модели используйте `LOCAL_MODEL=qwen2.5:3b` и при необходимости скорректируйте `MAX_TOKENS`, `NUM_CTX`, `TEMP` и `MEM_TURNS`. Тяжёлые (`qwen2.5:7b-instruct`, `qwen2.5-7b-long`) подключайте вручную.

---
# 🧠 Инструкция (короткая версия)

## Цель
LocalGPT — полностью локальный HR‑ и ASR‑бот. Все файлы внутри директории `LocalGPT/`.

---

## Структура
```
LocalGPT/
├── app/
├── web_ui/
├── ollama_models/
├── venv/
├── run_localgpt.py
└── .env
```

---

## Компоненты
- FastAPI — `/chat`, `/transcribe`.
- Ollama — LLM.
- faster‑whisper — ASR.
- web_ui — интерфейс.
- Modelfile — параметры LLM (`NUM_CTX`, `MAX_TOKENS`, `TEMP`).

---

## Запуск
```
cd LocalGPT
python3 run_localgpt.py
```
UI → http://127.0.0.1:8000/

`run_localgpt.py` пишет пошаговый лог: venv, `pip install`, проверка Ollama, `ollama pull`, открытие UI и запуск `uvicorn`.

---

## Работа GPT
- Редактировать только файлы внутри проекта.
- Новые файлы класть в app/, web_ui/ или корень.
- Не трогать venv/.
- Проверять пути.
- НЕ вызывать внешние API.
- Для транскрибации использовать `/transcribe` с параметрами:
  - `file`,
  - `model`: small / medium,
  - `prompt_preset`: none/ru/en.
  Whisper‑модели хранятся внутри проекта по пути `ollama_models/whisper/`.

---

## `.env`
```env
LOCAL_MODEL=qwen2.5:3b
LOCAL_BASE_URL=http://127.0.0.1:11434/v1
LOCAL_API_KEY=LOCAL-KEY
TEMP=0.25
MAX_TOKENS=512
NUM_CTX=32768
MEM_TURNS=6
```
Для long-контекста переключите `LOCAL_MODEL=qwen2.5-7b-long` и увеличьте `MAX_TOKENS`/`NUM_CTX`.

---

## Офлайн-подготовка
- Скачайте минимальную LLM через `ollama pull qwen2.5:3b` (тяжёлые — по желанию) и перенесите `~/.ollama/models`.
- Скачайте веса Whisper (`Systran/faster-whisper-*`) и положите в `ollama_models/whisper/`.
- В `.env` оставьте локальные `LOCAL_BASE_URL` (`http://127.0.0.1:11434/v1`) и `LOCAL_API_KEY`.

---

## Диагностика
- `curl -s http://127.0.0.1:8000/health`
