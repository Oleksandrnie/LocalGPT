# 🧠 Инструкция — короткая версия

## Что это

LocalGPT — локальный chat-first ассистент:
- FastAPI backend
- Ollama/OpenAI-compatible LLM
- faster-whisper для ASR
- SQLite для данных
- Caddy launcher для LAN/телефона

## Активные frontend-файлы

- `web_ui/gui_html.html`
- `web_ui/js/app.js`
- `web_ui/css/style.css`

Legacy JS-модули в `web_ui/js/` могут лежать в репозитории, но активная страница использует `app.js`.

## Ключевые UX-фичи

- список чатов слева
- поток сообщений по центру
- `+`-меню у composer
- микрофон в поле ввода
- browser TTS для озвучки
- профили и model settings в панели настроек
- LAN URL и shutdown в настройках

## Голос

- Voice input:
  `MediaRecorder` → `/transcribe` → Whisper `large-v3-turbo` → текст в textarea
- TTS:
  `window.speechSynthesis`, не локальная TTS-модель

## Модели и пути

Основные переменные:

```env
MODELS_DIR=models
WHISPER_MODELS_DIR=models/whisper
OLLAMA_MODELS_DIR=models/ollama
HF_CACHE_DIR=models/hf_cache
CTRANSLATE2_CACHE_DIR=models/ctranslate2_cache
LOCAL_BASE_URL=http://localhost:11434/v1
LOCAL_MODEL=qwen2.5:3b
TEMP=0.25
MAX_TOKENS=512
NUM_CTX=32768
MEM_TURNS=6
```

## Запуск

```bash
python3 run_localgpt.py
```

LAN:

```bash
./LTrnsrb.command
```
