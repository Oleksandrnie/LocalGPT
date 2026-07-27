# Тестирование LocalGPT

## Стратегия

Проверки идут от дешёвых к дорогим:

1. static checks;
2. unit tests с temporary data и mocks;
3. API/backend smoke;
4. manual UI regression;
5. live ASR/Ollama/TTS/OCR только когда задача действительно затрагивает runtime и пользователь готов к нагрузке.

Live workload не является частью обычного документационного или безопасного regression pass: он может загружать модели, CPU/GPU и нагревать Mac.

## Быстрые проверки

Из корня проекта:

```bash
git diff --check
venv/bin/python -m compileall -q app backend tests
node --check web_ui/js/app.js
node tests/markdown_rendering.test.mjs
```

Если `venv/` ещё не создан, сначала запустите LocalGPT или установите `app/requirements.txt` в отдельное окружение.

## Unit tests

Полный текущий Python suite:

```bash
venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

Точечные наборы:

| Подсистема | Команда |
| --- | --- |
| Chat routing, Ollama lifecycle, SSE и RAG integration | `venv/bin/python -m unittest tests.test_model_router -v` |
| ASR pipeline, memory и ASR context | `venv/bin/python -m unittest tests.test_pipeline_memory -v` |
| whisper.cpp backend | `venv/bin/python -m unittest tests.test_whisper_cpp_backend -v` |
| TTS routes | `venv/bin/python -m unittest tests.test_tts_routes -v` |
| Piper provider | `venv/bin/python -m unittest tests.test_piper_provider -v` |
| WAV post-processing | `venv/bin/python -m unittest tests.test_audio_postprocess_service -v` |
| OCR heuristics | `venv/bin/python -m unittest tests.test_ocr_service -v` |
| Plugin Registry и Tailscale handler | `venv/bin/python -m unittest tests.test_plugin_registry -v` |
| Model installation state | `venv/bin/python -m unittest tests.test_model_install_state -v` |

Tests используют `unittest`; отдельные cases создают temporary SQLite/files и patch внешние процессы. Перед live-запуском всё равно проверяйте конкретный test body на обращение к локальным моделям/CLI.

## Backend smoke

Терминал 1:

```bash
venv/bin/python -m uvicorn backend.server:app --host 127.0.0.1 --port 8000
```

Терминал 2:

```bash
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8000/ui/gui_html.html
```

Smoke считается пройденным, если `/health` возвращает `status: ok`, UI отдаётся без 5xx, а запуск не создаёт неожиданных tracked files. Если порт занят, используйте свободный порт или штатный launcher.

## Проверки подсистем

### Chat и providers

- manual/auto model selection не загружает модель без явного действия;
- missing/partial/installed/active states не смешиваются;
- `stream=true` создаёт SSE `delta`, а reconnect не дублирует текст;
- non-streaming сохраняет тот же assistant lifecycle;
- RAG context попадает в prompt только активного профиля;
- profile prompt, memory, criteria и language policy сохраняют порядок.

### ASR

- быстрый voice-to-input и ASR Studio остаются разными UX flows;
- backend selection соответствует `WHISPER_BACKEND`;
- disabled stage не запускается ни одним analysis mode;
- `full` требует `asr_full_analysis_enabled`;
- ASR context индексируется, ищется и удаляется вместе со связанной записью.

Не запускать live transcription/full pipeline без осознанной проверки ресурсов.

### TTS

- health/voices/library endpoints работают без повреждения history;
- provider корректно обрабатывает missing runtime/model;
- generation пишет output и history;
- speed processing создаёт валидный WAV и не перезаписывает исходник неожиданно.

### OCR

- API принимает только поддерживаемые изображения;
- отсутствующий Tesseract возвращает понятную ошибку;
- language fallback и UI-noise cleanup не удаляют значимый текст.

### RAG

- profile isolation;
- `.txt`, `.md`, `.json` validation;
- MD→JSON generation и force reindex;
- chunk overlap, embedding metadata и top-k search;
- context assembly соблюдает `max_chars`;
- file/context deletion очищает DB records.

### Plugins и networking

- malformed manifest остаётся видимым как invalid/untrusted;
- untrusted plugin нельзя effectively enable;
- docs path не выходит из plugin directory;
- Tailscale checks read-only и не запускают Serve/Funnel;
- core LAN/Tailscale addresses возвращаются backend-ом, а не hardcode-ятся UI.

## UI regression

Минимальная ручная матрица:

- desktop и mobile viewport;
- dark/light theme;
- sidebar, chat library, scroll-to-latest;
- profiles/sessions и Settings tabs;
- streaming и refresh/reconnect;
- ASR/TTS/OCR tool docks;
- RAG panel и context section;
- Plugins и network-address menu;
- keyboard focus, aria states и reduced-motion-sensitive flows.

Активный UI — `web_ui/gui_html.html` + `web_ui/js/app.js`. Старый modular flow под `web_ui/js/main.js` не подключён HTML entry point и не должен считаться текущим runtime без отдельной миграции.

## Platform-specific

- macOS: `.command` launchers, Caddy certificate trust, whisper.cpp Metal/CoreML, microphone permissions;
- Windows: `start_localgpt.bat`, Python launcher resolution, filesystem paths;
- Linux: executable bit на shell scripts, `ffmpeg`, Tesseract и Ollama service.

## Критерии прохождения

- команды завершаются с exit code 0;
- нет новых traceback, 5xx, зависших tasks или tracked runtime artifacts;
- тесты не используют реальные модели без явного намерения;
- изменения UI проверены в затронутых viewport/theme состояниях;
- документация и команды соответствуют текущему коду.

## Известные ограничения

- автоматизированного end-to-end browser suite в репозитории нет;
- live ASR/LLM/TTS/OCR зависит от установленных binaries, моделей и hardware;
- LAN/Tailscale требуют проверки в реальной сети;
- manual accessibility и mobile regression остаются обязательными для заметных UI-изменений.
