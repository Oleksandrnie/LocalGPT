

# 🧠 Инструкция для ChatGPT (короткая версия)

## 🎯 Цель
**LocalGPT** — локальный HR- и ASR-бот, работающий полностью офлайн на Mac M1 Pro без внешних API.  
Все файлы и данные находятся в одной папке:
```
/Users/oleksandrniemchenko/my_personal_files/LocalGPT
```

---

## 🧱 Структура проекта
```
LocalGPT/
├── app/               # Backend (FastAPI)
├── web_ui/            # Frontend (HTML + JS)
├── ollama_models/     # Локальные LLM-модели
├── venv/              # Виртуальное окружение Python
├── run_localgpt.sh    # Скрипт запуска всего стека
├── .env               # Настройки окружения
└── INSTRUCTIONS_FOR_GPT.md / SHORT.md
```

---

## ⚙️ Основные компоненты

| Компонент | Назначение |
|------------|-------------|
| **FastAPI (app/server.py)** | REST API `/chat`, `/transcribe`, `/health`, `/version` |
| **Ollama** | Локальный LLM-сервис |
| **faster-whisper** | Распознавание речи |
| **web_ui/gui_html.html** | Минималистичный веб-интерфейс |
| **ollama_models/qwen2.5-7b-long** | Кастомная модель LLM |
| **.env** | Переменные окружения |
| **run_localgpt.sh** | Запуск API + UI |

---

## 🚦 Правила работы GPT с проектом

1. Все файлы находятся **внутри** `/Users/oleksandrniemchenko/my_personal_files/LocalGPT/`.
2. **Не создавать файлы вне директории проекта.**
3. **Редактировать только существующие файлы**, используя точечные инструкции (`edit_file`).
4. Новые файлы размещать строго:
   - Backend → `app/`
   - Frontend → `web_ui/`
   - Скрипты → корень проекта.
5. Не трогать `venv/` и системные кеши.
6. Все пути — относительные от корня проекта.

---

## ⚙️ Добавление зависимостей
- Записывать новые пакеты в `app/requirements.txt`.
- После этого:
  ```bash
  source venv/bin/activate
  pip install -r app/requirements.txt
  ```

---

## 🚀 Запуск
Из терминала:
```bash
~/my_personal_files/LocalGPT/run_localgpt.sh
```
Откроется интерфейс по адресу:
```
http://127.0.0.1:8000/
```
Алиас для быстрого старта:
```bash
alias localgpt='~/my_personal_files/LocalGPT/run_localgpt.sh'
```

---

## 🧩 Работа GPT
GPT должен:
- Понимать структуру проекта и назначение директорий.  
- Проверять корректность путей перед изменениями.  
- Не создавать дубликаты `FastAPI(app=...)`.  
- Сохранять компактный контекст (учитывать переменную `MEM_TURNS`).  
- Предупреждать, если путь или команда выходят за пределы проекта.  
- Работать **только локально**, без внешних API (OpenAI, HF и т.д.).

---

## 🧾 Диагностика

| Проверка | Команда |
|-----------|----------|
| Ollama запущен | `curl -s http://127.0.0.1:11434/v1/models` |
| API жив | `curl -s http://127.0.0.1:8000/health` |
| Версия | `curl -s http://127.0.0.1:8000/version` |
| Модели | `ollama list` |

---

## ⚙️ Кастомная модель Ollama
Файл: `ollama_models/qwen2.5-7b-long/Modelfile`
```
FROM qwen2.5:7b-instruct
PARAMETER num_ctx 32768
PARAMETER num_predict 1024
PARAMETER temperature 0.2
PARAMETER mirostat 2
TEMPLATE """{{ .System }}
{{ .Prompt }}"""
```
Пересборка:
```bash
ollama create qwen2.5-7b-long -f ollama_models/qwen2.5-7b-long/Modelfile
```

---

## 🧩 Файл `.env`
Пример:
```
MODEL=qwen2.5-7b-long
TEMPERATURE=0.2
MEM_TURNS=6
WHISPER_COMPUTE_TYPE=int8
ADMIN_TOKEN=local-admin-123
```

---

## 🧩 Рекомендации
- Используй `temperature=0.2` для стабильности.
- Следи, чтобы история не превышала `MEM_TURNS`.
- Не генерируй ответы >1200 токенов.
- Проверяй структуру проекта перед правками.

---

## 🔒 Ограничения
- Только локальные операции (без внешних API).  
- Совместимость с macOS ARM (M1/M2).  
- GPT не должен изменять виртуальное окружение или глобальные настройки.

---

🟢 **Эта инструкция должна быть системным контекстом при работе ChatGPT с проектом LocalGPT.**