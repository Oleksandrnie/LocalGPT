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

Setup/bootstrap contract без запуска package installers:

```bash
venv/bin/python -m py_compile setup/setup_localgpt.py tests/test_setup_dependencies.py
venv/bin/python -m unittest tests.test_setup_dependencies -v
/bin/sh -n setup/setup_localgpt.sh
/bin/zsh -n setup/setup_localgpt.command
```

`setup/setup_localgpt.py --verify-only` только проверяет текущее окружение, но возвращает non-zero при отсутствующих обязательных runtime components.

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
| Chat image storage, lifecycle, vision runtime/settings и RAG export | `venv/bin/python -m unittest tests.test_chat_attachments tests.test_chat_vision_context tests.test_chat_vision_lifecycle tests.test_chat_vision_runtime tests.test_vision_settings tests.test_vision_rag -v` |
| ASR pipeline, memory и ASR context | `venv/bin/python -m unittest tests.test_pipeline_memory -v` |
| whisper.cpp backend | `venv/bin/python -m unittest tests.test_whisper_cpp_backend -v` |
| TTS routes | `venv/bin/python -m unittest tests.test_tts_routes -v` |
| Piper provider | `venv/bin/python -m unittest tests.test_piper_provider -v` |
| WAV post-processing | `venv/bin/python -m unittest tests.test_audio_postprocess_service -v` |
| OCR heuristics | `venv/bin/python -m unittest tests.test_ocr_service -v` |
| Plugin Registry и Tailscale handler | `venv/bin/python -m unittest tests.test_plugin_registry -v` |
| Model installation state | `venv/bin/python -m unittest tests.test_model_install_state -v` |
| Ollama pull API/CLI compatibility | `venv/bin/python -m unittest tests.test_ollama_pull -v` |
| Model export/import bundle | `venv/bin/python -m unittest tests.test_model_transfer_manifest tests.test_model_transfer_inventory tests.test_model_transfer_export tests.test_model_transfer_import -v` |

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
- PNG/JPEG/WebP upload проверяет profile ownership, count/byte/pixel/side limits и не сохраняет binary в message/RAG;
- direct image route доступен только при runtime-confirmed `vision`, а text-only model использует явный context route;
- Vision context size сохраняется в profile settings и уходит в native Ollama как `options.num_ctx` для direct/streaming inference;
- attachment lifecycle связан с persisted user message/task, refresh/cancel и cleanup не оставляют active record в неверном terminal state.

Static UI contract для attachment composer, Vision tab и explicit RAG export:

```bash
node tests/chat_attachments_ui.test.mjs
```

System Settings model-transfer contract:

```bash
node tests/model_transfer_ui.test.mjs
```

Model-transfer tests используют только temporary synthetic files. Реальный export/import локальных моделей запускается отдельно явным действием пользователя.

Контролируемый live vision smoke запускается отдельно после явной установки модели. Используйте маленькое детерминированное изображение, `temperature=0`, ограниченный `max_tokens`, последовательный запуск и `keep_alive=0`; проверьте точный текст/формы, отсутствие CPU fallback, terminal task/attachment state, отсутствие binary/path в messages и пустой `ollama ps` после теста. Не загружайте 3B и 7B одновременно на 16 GB машине.

Если Ollama сообщает `request (...) exceeds the available context size (4096)`, откройте Settings → Vision → `Vision context, токены`, сохраните 8192 (для более длинной истории — 16384) и повторите запрос. Значение применяется к следующему vision task.

### ASR

- быстрый voice-to-input и ASR Studio остаются разными UX flows;
- chat-диктовка использует language/prompt preset активного профиля; запись короче 700 мс не отправляется в ASR;
- `whisper.cpp` использует Silero VAD, чтобы тишина не превращалась в вымышленную транскрипцию;
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
- validation только `.md` и отклонение legacy `.txt`/`.json`;
- force reindex очищает stale JSON records, не удаляя legacy files;
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
- image picker/paste/drop, attachment preview/remove/history и Vision → RAG dialog;
- Vision settings/library, runtime capability state и cache cleanup;
- Plugins и network-address menu;
- keyboard focus, aria states и reduced-motion-sensitive flows.

Активный UI — `web_ui/gui_html.html` + `web_ui/js/app.js`. Старый modular flow под `web_ui/js/main.js` не подключён HTML entry point и не должен считаться текущим runtime без отдельной миграции.

## Platform-specific

- macOS: `.command` launchers, Caddy certificate trust, whisper.cpp Metal/CoreML, microphone permissions;
- Windows: `start_localgpt.bat`, Python launcher resolution, filesystem paths;
- Linux: executable bit на shell scripts, `ffmpeg`, Tesseract и Ollama service.

## Setup/bootstrap acceptance на новом окружении

Эта проверка намеренно ручная: она устанавливает system packages и может запросить administrative privileges.

1. На чистом macOS/Linux/Windows environment запустить соответствующий `setup/setup_localgpt.*` entry point.
2. Проверить корректное определение ОС и package manager, понятные confirmation prompts и отсутствие model downloads. На macOS убедиться, что `models/whisper_cpp/bin/whisper-cli` собран и исполняем.
3. Согласиться на core dependencies; optional Caddy/Tailscale/Node проверить отдельно по нужному режиму.
4. Убедиться, что final verification проходит и `venv/` содержит imports из `app/requirements.txt`.
   Отдельный `.venv/`, если он существовал до setup, должен остаться нетронутым и не считаться штатным runtime environment.
5. Повторить setup: установленные system tools должны быть пропущены, pip не должен ломать environment.
6. Запустить `start_localgpt*`, проверить `/health` и `/ui/gui_html.html` по Backend smoke выше.
7. Убедиться, что `.env`, models, RAG sources, profiles и public networking не создавались автоматически.

Результаты platform acceptance фиксируются в активном task progress до финального cleanup.

## Критерии прохождения

- команды завершаются с exit code 0;
- нет новых traceback, 5xx, зависших tasks или tracked runtime artifacts;
- тесты не используют реальные модели без явного намерения;
- изменения UI проверены в затронутых viewport/theme состояниях;
- документация и команды соответствуют текущему коду.

## Известные ограничения

- автоматизированного end-to-end browser suite в репозитории нет;
- live ASR/LLM/TTS/OCR зависит от установленных binaries, моделей и hardware;
- vision output зависит от модели; smoke должен проверять заранее известные признаки изображения, а не точную формулировку ответа;
- LAN/Tailscale требуют проверки в реальной сети;
- manual accessibility и mobile regression остаются обязательными для заметных UI-изменений.
