# Providers

В LocalGPT нет одного универсального provider API. Provider-like границы разделены по назначению: chat/Ollama runtime, ASR backend и формальный TTS contract.

## Chat и Ollama

`backend/apps/chat/services/ollama_runtime.py` — низкоуровневый клиент локального Ollama:

- normal, streaming и native multimodal `/api/chat`;
- передаёт `temperature`, `num_predict` и явный `options.num_ctx`, чтобы Ollama не использовал неявный default context 4096;
- model load/unload и active runners;
- `keep_alive`, `think` и Metal→CPU fallback;
- принудительная остановка зависших runners в ограниченных recovery flows.

Native `message.thinking` и `message.content` нормализуются в разные result/event поля. Thinking OFF передаёт `think=false`; для hybrid Qwen к копии последнего user turn добавляется transient `/no_think`, который не сохраняется. Thinking ON использует native structured reasoning. Reasoning никогда не возвращается строковыми compatibility APIs и не смешивается с final stream.

Ollama предоставляет один `num_predict`, поэтому `output_tokens` и `thinking_tokens` не выдаются за два provider hard limits. OFF отправляет output budget; ON отправляет safety-capped сумму allowances для одного inference, а effective settings явно сообщают `native_reasoning_budget_supported=false`. Reasoning-only `done_reason=length` считается incomplete final answer. Конкретный локальный Modelfile может не соблюдать OFF; такой manifest нужно обновить, а не разбирать reasoning-like `content` эвристиками.

`model_residency.py` управляет target-model policy отдельно от router model. Ручной и auto режимы могут использовать разные `keep_alive`; target limit предотвращает накопление тяжёлых моделей.

`model_router.py`:

- использует utility model `qwen3:0.6b`;
- принимает только известные intents;
- принудительно сопоставляет intent и разрешённую target model;
- корректирует явные code и простые RAG lookup запросы;
- использует fallback при invalid JSON или низкой confidence;
- не выбирает Local Calculator автоматически.

Model discovery и install state принадлежат `app/services/models.py`. Состояния различают configured, installed, active, downloading, partial и missing; наличие orphan partial blob не равно установленной runtime-модели. Загрузка модели предпочитает native `POST /api/pull` со stream-NDJSON прогрессом. Если endpoint отсутствует, используется совместимый CLI fallback `ollama pull <model>` без `--json`: этот флаг не является аргументом `ollama pull`, поэтому отсутствие флага не означает старую версию Ollama. Для диагностики задача загрузки логирует путь CLI из `PATH`, его версию, безопасно отредактированный endpoint, transport и stderr/error.

### Vision-модели

Vision library отделена от обычного chat catalog:

| Model id | Назначение | Примерный размер |
| --- | --- | --- |
| `qwen2.5vl:3b` | рекомендуемый основной профиль | 3.2 GB |
| `qwen2.5vl:7b` | более качественный профиль для сложных изображений | 6.0 GB |
| `gemma3:4b` | альтернативный сравнительный профиль | 3.3 GB |

Catalog capability — декларация UI, но direct image route разрешён только установленной модели, для которой текущий Ollama runtime подтвердил capability `vision`. `app/services/models.py` читает structured metadata, когда CLI его поддерживает, и парсит plain `ollama show` как совместимый fallback. Неподтверждённая capability не превращается в silent fallback.

`backend/apps/chat/services/vision_runtime.py`:

- обходит text intent router для image request;
- в `auto` предпочитает catalog order, начиная с `qwen2.5vl:3b`;
- добавляет base64 images только к копии последнего user message и только на время запроса;
- ограничивает суммарный размер и одновременно выполняет не больше одного vision inference;
- для выбранной text-only модели строит `vision_context`, затем передаёт его выбранной response model;
- возвращает явную ошибку, если fallback запрещён или подходящей vision-модели нет.

OCR assist (`auto`, `on`, `off`) добавляет помеченные per-image evidence; `ocr_only` — отдельный явно degraded route, а не скрытая замена vision.

Для image chat profile setting `vision_num_ctx` применяется к direct vision analysis/generation. Значение по умолчанию — 8192, допустимый диапазон — 4096–131072; text-only response в `vision_context` fallback использует обычный model `num_ctx`. Больший context помогает вместить визуальные токены и историю, но увеличивает расход памяти.

## ASR backends

Конфигурация `WHISPER_BACKEND` принимает:

- `whisper_cpp` — явный whisper.cpp;
- `faster_whisper` — Python/CTranslate2;
- `auto` — whisper.cpp при готовом binary/model, иначе faster-whisper.

`backend/apps/asr/whisper.py` выбирает backend и нормализует общий результат. `whisper_cpp.py` владеет binary/model/VAD discovery, command execution и подготовкой путей: штатный запуск включает Silero VAD, подавление non-speech tokens и отключение temperature fallback, чтобы тишина не становилась вымышленной транскрипцией. `downloads.py` управляет model preparation/update state.

Основные параметры находятся в `.env.example`: model, device, compute type, beam size, binary, threads, model path, FFmpeg и CoreML download policy. На macOS setup также устанавливает небольшой `ggml-silero-v6.2.0.bin`; параметры VAD зафиксированы runtime-ом и покрыты backend tests.

## TTS contract

`backend/apps/tts/providers/base.py` определяет:

- `VoiceDefinition`;
- `SynthesisResult`;
- abstract `TTSProvider.is_available()`;
- `list_voices()`;
- `get_voice()`;
- `synthesize()`.

`PiperProvider` — текущая реализация. Она:

- обнаруживает `.onnx` и JSON config;
- поддерживает multi-speaker voices;
- читает remote catalog через Piper voice helpers;
- загружает/удаляет voice artifacts;
- разбивает длинный текст на chunks;
- синтезирует WAV и возвращает duration.

Provider instance создаётся service layer; HTTP router не должен знать детали Piper runtime.

## Перенос локальных моделей

Transfer inventory использует configured paths и существующие provider boundaries. Переносятся только complete Ollama manifests со всеми blobs, готовая faster-whisper directory, whisper.cpp GGML с найденными CoreML assets и Piper `.onnx` + `.onnx.json`. Import не переносит runtime binaries/settings, не перезаписывает отличающиеся существующие файлы и публикует Ollama manifest после blobs. После успеха UI перечитывает обычные provider inventories.

## Lifecycle и ошибки

Общий принцип:

1. configuration/discovery;
2. availability check;
3. explicit user action;
4. task execution;
5. persisted/local result;
6. cancel/error cleanup.

Внешние зависимости должны давать различимые ошибки: отсутствующий binary, model, runtime package, network/catalog, invalid voice или exhausted resources. Не подменяйте missing dependency успешным пустым результатом.

## Добавление provider

Для TTS:

- реализовать `TTSProvider`;
- не менять public route contract без необходимости;
- определить discovery, model files, cleanup и error mapping;
- добавить provider/unit tests и health coverage.

Для нового chat/ASR backend сначала нужен отдельный contract design: текущие интерфейсы завязаны на Ollama и whisper result shapes. Не добавляйте условные ветки во все routers; изолируйте их в service/provider boundary.

## Проверки

См. [TESTING.md](../TESTING.md): `test_model_router`, `test_model_install_state`, `test_whisper_cpp_backend`, `test_piper_provider`, `test_tts_routes`.
