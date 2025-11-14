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
- Modelfile — параметры LLM.

---

## Запуск
```
cd LocalGPT
python3 run_localgpt.py
```
UI → http://127.0.0.1:8000/

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

## Диагностика
- `curl -s http://127.0.0.1:8000/health`