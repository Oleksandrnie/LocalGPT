# 🧠 Инструкция (короткая версия)

## Цель
LocalGPT — полностью локальный HR‑ и ASR‑бот. Все файлы внутри директории `LocalGPT/`.

---

## Структура
```
LocalGPT/
├── app/
├── web_ui/
├── ollama_models/            # ollama_models/models — пустая по умолчанию, .gitkeep
├── venv/
├── run_localgpt.py
└── .env
├── Instructions_for_GPT_Context.md  # описание текущей памяти/контекста
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
- История транскрибаций: компактный список с кнопками использовать / редактировать / удалить; детали и переименование открываются в модалке по центру.
- Для транскрибации использовать `/transcribe` с параметрами:
  - `file`,
  - `model`: small / medium,
  - `prompt_preset`: none/ru/en.
  Whisper‑модели хранятся внутри проекта по пути `ollama_models/whisper/`.
- Модели Ollama хранятся в `ollama_models/models/` (игнор в git). Если нет локальных моделей и активных загрузок, автоматически запускается скачивание минимальной (`qwen2.5:3b` по умолчанию). Есть API для остановки загрузки: `/models/pull/{task_id}/cancel`; кнопка удаления активна только для скачанных моделей.

---

## `.env`
```env
LOCAL_MODEL=qwen2.5:7b-instruct
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
- Скачайте LLM через `ollama pull qwen2.5:7b-instruct` и перенесите `~/.ollama/models`.
- Скачайте веса Whisper (`Systran/faster-whisper-*`) и положите в `ollama_models/whisper/`.
- В `.env` оставьте локальные `LOCAL_BASE_URL` (`http://127.0.0.1:11434/v1`) и `LOCAL_API_KEY`.

---

## Диагностика
- `curl -s http://127.0.0.1:8000/health`
