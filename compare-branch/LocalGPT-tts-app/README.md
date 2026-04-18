# LocalGPT TTS / Voice

Локальный TTS-инструмент на `FastAPI + WebUI + project-local storage`.

Что делает приложение:
- принимает текст;
- показывает доступные локальные Piper-голоса;
- показывает каталог Piper voices с quality и language;
- догружает новые голоса в `models/tts/piper/`;
- делает локальное preview уже скачанных голосов;
- генерирует базовый `WAV`;
- позволяет применить ускорение `1.0x`-`2.0x`;
- хранит историю и все аудиофайлы внутри проекта.

Никакие данные не отправляются во внешние inference API.

## Стек
- Python
- FastAPI
- Piper (`piper-tts`)
- HTML / CSS / JavaScript
- `ffmpeg` для post-process speed

## Структура хранения
- Голоса Piper: `models/tts/piper/`
- История: `app/data/tts/history/`
- Готовые WAV: `app/data/tts/output/`
- Временные файлы: `app/data/tts/temp/`

Для одного Piper-голоса ожидаются как минимум два файла:
- `voice-name.onnx`
- `voice-name.onnx.json`

Пример:
```text
models/tts/piper/en_US-lessac-medium.onnx
models/tts/piper/en_US-lessac-medium.onnx.json
```

## Запуск
```bash
python3 run_localgpt.py
```

Ручной запуск:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r app/requirements.txt
uvicorn app.server:app --host 127.0.0.1 --port 8000 --reload
```

UI:
```text
http://127.0.0.1:8000/ui/gui_html.html
```

## Зависимости окружения
- Python 3.13+
- `ffmpeg`
- хотя бы один локальный Piper voice model в `models/tts/piper`

Проверка `ffmpeg`:
```bash
ffmpeg -version
```

## API
- `GET /tts/health`
- `GET /tts/voices`
- `GET /tts/voice-library`
- `POST /tts/voice-library/download`
- `GET /tts/voice-library/download/{task_id}`
- `POST /tts/voice-library/preview`
- `POST /tts/generate`
- `POST /tts/process-speed`
- `GET /tts/history`
- `GET /tts/history/{id}`
- `DELETE /tts/history/{id}`
- `GET /tts/output/{id}?variant=base`
- `GET /tts/output/{id}?variant=processed&speed=1.25`

## Формат записи истории
Каждая запись хранит:
- `id`
- `created_at`
- `updated_at`
- `text`
- `preview`
- `voice_id`
- `voice_name`
- `voice_language`
- `provider`
- `base_output_path`
- `processed_output_path`
- `processed_outputs`
- `speed`
- `duration_sec`
- `processed_duration_sec`
- `status`
- `error`

## Конфигурация
Смотрите `.env` и `.env.example`.

Ключевые переменные:
- `TTS_ENABLED=1`
- `TTS_DEFAULT_PROVIDER=piper`
- `TTS_MODELS_DIR=models/tts`
- `TTS_OUTPUT_DIR=app/data/tts/output`
- `TTS_HISTORY_DIR=app/data/tts/history`
- `TTS_TEMP_DIR=app/data/tts/temp`
- `TTS_AUDIO_FORMAT=wav`
- `TTS_MAX_TEXT_CHARS=15000`
- `TTS_SPEED_OPTIONS=1.0,1.25,1.5,1.75,2.0`

## UI сценарий
1. Ввести текст.
2. При необходимости открыть `Voice Library` и догрузить новый Piper voice.
3. Посмотреть его quality и language.
4. Запустить локальное preview скачанного голоса.
5. Выбрать голос.
6. Нажать `Generate`.
7. Дождаться базового `WAV`.
8. Прослушать результат.
9. Выбрать скорость.
10. Нажать `Применить`.
11. Прослушать ускоренный `WAV`.
12. Скачать нужный файл.

## Smoke checklist
1. `GET /tts/health` отвечает.
2. `GET /tts/voices` показывает локальные голоса.
3. Генерация создаёт `WAV` в `app/data/tts/output`.
4. Speed processing создаёт отдельный `WAV`, не затирая base.
5. История сохраняется в `app/data/tts/history`.
6. UI воспроизводит base и processed аудио.
