# LocalGPT TTS Context

LocalGPT в этой ветке — локальный TTS-инструмент.

Технологии:
- FastAPI backend
- HTML/CSS/JS WebUI
- Piper как TTS provider
- локальное файловое хранение внутри проекта

Ключевые каталоги:
- `app/routers/tts.py`
- `app/services/tts_service.py`
- `app/services/audio_postprocess_service.py`
- `app/providers/tts/`
- `app/data/tts/`
- `models/tts/piper/`

Основной пользовательский сценарий:
1. ввести текст;
2. выбрать локальный голос;
3. нажать `Generate`;
4. получить базовый `WAV`;
5. при необходимости применить speed post-process;
6. скачать base или processed `WAV`.

API:
- `GET /tts/health`
- `GET /tts/voices`
- `POST /tts/generate`
- `POST /tts/process-speed`
- `GET /tts/history`
- `GET /tts/history/{id}`
- `DELETE /tts/history/{id}`
- `GET /tts/output/{id}`
