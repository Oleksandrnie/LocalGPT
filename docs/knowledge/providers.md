# Providers

В LocalGPT нет одного универсального provider API. Provider-like границы разделены по назначению: chat/Ollama runtime, ASR backend и формальный TTS contract.

## Chat и Ollama

`backend/apps/chat/services/ollama_runtime.py` — низкоуровневый клиент локального Ollama:

- normal, streaming и native multimodal `/api/chat`;
- передаёт `temperature`, `num_predict` и явный `options.num_ctx`, чтобы Ollama не использовал неявный default context 4096;
- model load/unload и active runners;
- `keep_alive`, `think` и Metal→CPU fallback;
- принудительная остановка зависших runners в ограниченных recovery flows.

Native `message.thinking` и `message.content` нормализуются в разные result/event поля. Thinking ON использует native structured reasoning. OFF для обычных моделей передаёт `think=false`; для hybrid Qwen к копии последнего user turn добавляется transient `/no_think`, но native flag намеренно не передаётся. Это сохраняет структурный parser у Modelfile, который безусловно открывает `<think>`, и не позволяет превратить reasoning в обычный content. OFF reasoning проверяется privacy guard, но не отправляется клиенту и не сохраняется. Reasoning никогда не возвращается строковыми compatibility APIs и не смешивается с final stream.

`ChatService` не полагается на отказ модели как на privacy boundary. Перед выдачей non-streaming content/reasoning он блокирует буквальное повторение длинных secret-like значений из backend/profile prompt layers и явно помеченного private session context. Streaming guard удерживает хвост длиной до самого длинного protected literal и проверяет его до отправки; direct vision stream использует ту же проверку. User-query markers не повышаются до protected values.

Ollama предоставляет один `num_predict`, поэтому `output_tokens` и `thinking_tokens` не выдаются за два provider hard limits. Default для thinking budget — 4096 токенов, минимум — 2048, максимум поля — 32768; ранее сохранённые меньшие значения нормализуются в effective settings без миграции БД, а более высокие overrides сохраняются. ON отправляет safety-capped сумму allowances на каждый inference. Обычный OFF использует только output allowance; hybrid Qwen OFF использует сумму output + thinking как compatibility cap, потому что его manifest может выполнить скрытый structural reasoning даже после `/no_think`. Пользователю всё равно выдаётся только final content, а effective settings явно сообщают `native_reasoning_budget_supported=false`. Эти значения — provider allowance, а не гарантия, что модель потратит весь бюджет на reasoning. Provider boundary разбирает только нативные structural fields; эвристическое распознавание reasoning-like фраз не используется.

`services/continuation.py` продолжает генерацию только после явного `done_reason=length` с непустым final content: максимум четыре дополнительных вызова после первого. Каждый вызов сохраняет модель, исходные инструкции/evidence и тот же per-call token budget/settings; к исходным messages добавляются уже полученный assistant text и backend-owned continuation request. Retrieval и image/RAG routing повторно не выполняются; direct Vision получает те же image paths на каждом проходе, а явный RAG-vision analysis и text response используют этот же bounded contract отдельно. Exact suffix/prefix overlap удаляется; отсутствие нового текста прекращает дальнейшие попытки как incomplete. Empty/reasoning-only, normal stop, cancel и provider failure не запускают продолжение. Исчерпание cap остаётся `chat_final_answer_incomplete` (502): assistant row очищается и не входит в completed history/summary. Non-streaming проверяет склеенный content/reasoning privacy guard; streaming сохраняет guard tail через границы проходов и публикует единственный terminal event. Первый проход стримится обычно, последующие bounded проходы буферизуются до удаления overlap.

`model_residency.py` управляет target-model policy отдельно от router model. Ручной и auto режимы могут использовать разные `keep_alive`; target limit предотвращает накопление тяжёлых моделей.

`model_router.py`:

- использует utility model `qwen3:0.6b`;
- принимает только известные intents;
- принудительно сопоставляет intent и разрешённую target model;
- корректирует явные code и простые RAG lookup запросы;
- использует fallback при invalid JSON или низкой confidence;
- не выбирает Local Calculator автоматически.

Model discovery и install state принадлежат `app/services/models.py`. Состояния различают configured, installed, active, downloading, partial и missing; наличие orphan partial blob не равно установленной runtime-модели. Загрузка модели предпочитает native `POST /api/pull` со stream-NDJSON прогрессом. Если endpoint отсутствует, используется совместимый CLI fallback `ollama pull <model>` без `--json`: этот флаг не является аргументом `ollama pull`, поэтому отсутствие флага не означает старую версию Ollama. Для диагностики задача загрузки логирует путь CLI из `PATH`, его версию, безопасно отредактированный endpoint, transport и stderr/error.

Settings → Chat/LLM exposes a self-service Ollama model installer backed by the same pull task/API and cancel lifecycle. It accepts a bounded model reference or a narrowly parsed snippet containing one `ollama pull <model>` and, optionally, an exact matching `ollama run <model>` line. The parser only extracts the pull target; it never executes pasted text, shell syntax or `ollama run`. Backend validation independently rejects commands/options before starting a pull. After the next installed-inventory refresh, non-catalog installed models are included in chat selectors; configured utility/Vision models remain in their own lanes and confirmed embedding-only models are excluded. Download still requires confirmation and never changes the selected model automatically. The installer is Ollama-only; downloaded models must be compatible with chat to be useful in the chat selector.

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
- для выбранной text-only chat-модели обычный image request выполняет сама настроенная Vision-модель; второй text-only проход не запускается;
- возвращает явную ошибку, если fallback запрещён или подходящей vision-модели нет.

При text-only выбранной chat-модели обычный image request маршрутизируется прямо в настроенную multimodal Vision-модель: она получает system policies, текущую команду, image binary и необязательное помеченное OCR evidence, сама выполняет команду и сохраняется как фактическая модель ответа. Старые сообщения и автоматический RAG в этот turn не попадают. Двухмодельный `vision_context` остаётся только для явного запроса объединить изображение с RAG/базой знаний/загруженными документами: Vision сначала извлекает визуальные факты, затем выбранная chat-модель объединяет их с актуальным RAG envelope. `ollama_think` text-модели не передаётся отдельной Vision-модели, а `keep_alive=0` гарантирует последовательную выгрузку на локальном Mac.

OCR assist (`auto`, `on`, `off`) добавляет помеченные per-image evidence; `ocr_only` — отдельный явно degraded route, а не скрытая замена vision.

Для image chat profile setting `vision_num_ctx` применяется к direct vision analysis/generation. Значение по умолчанию — 8192, допустимый диапазон — 4096–131072; text-only response в `vision_context` fallback использует обычный model `num_ctx`. Больший context помогает вместить визуальные токены и историю, но увеличивает расход памяти.

Отдельный `vision_output_tokens` ограничивает только ответ Vision: default и рекомендуемый базовый лимит — 1024, допустимое явное значение — 128–8192. Legacy `0` (в том числе сохранённый в существующем профиле) разрешается в 1024 при чтении preferences и выполнении запроса, без обязательной перезаписи SQLite; API также принимает `0` как compatibility alias для 1024. Наследования text `output_tokens` больше нет. Ниже 1024 ставить не рекомендуется из-за риска обрыва; большим таблицам может потребоваться больше, и 1024 не гарантирует точность или полноту любого изображения. Настройка применяется к direct image completion и промежуточному Vision-анализу перед явным Chat/RAG fallback; обычные text-only ответы используют исходный `output_tokens`. Provider result/event сохраняет `done_reason` и `eval_count`, поэтому ответ, оборванный с `done_reason=length`, не публикуется как завершённый и не попадает в историю как полный.

## ASR backends

Асинхронные `/transcribe/tasks` выполняются последовательно в process-local FIFO: `queued` не является terminal state и не запускает provider до освобождения единственного child-process slot. Синхронный `/transcribe` не входит в этот scheduler.

Конфигурация `WHISPER_BACKEND` принимает:

- `whisper_cpp` — явный whisper.cpp;
- `faster_whisper` — Python/CTranslate2;
- `auto` — whisper.cpp при готовом binary/model, иначе faster-whisper.

`backend/apps/asr/whisper.py` выбирает backend и нормализует общий результат. `whisper_cpp.py` владеет binary/model/VAD discovery, command execution и подготовкой путей: штатный запуск включает Silero VAD, подавление non-speech tokens и отключение temperature fallback. После приведения к PCM backend также отклоняет заведомо пустой/тихий сигнал до inference и консервативно отбрасывает короткий результат, целиком совпадающий с типовым credit-артефактом субтитров. No-speech возвращается как `empty_transcription` с сообщением `Речь в аудиофайле не обнаружена` и не сохраняется в transcript storage. `downloads.py` управляет model preparation/update state.

macOS setup создаёт `models/whisper_cpp/bin/whisper-cli` как относительную ссылку на собранный binary внутри `models/whisper_cpp/source/build`, сбрасывает stale generated CMake cache после перемещения checkout и добавляет relocatable `@loader_path` для локальных dylib. Повторная подготовка заменяет устаревшую или сломанную ссылку.

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

Transfer inventory использует configured paths и существующие provider boundaries. Переносятся только complete Ollama manifests со всеми blobs, готовая faster-whisper directory, whisper.cpp GGML с найденными CoreML assets и Piper `.onnx` + `.onnx.json`. Chat, Vision и embedding tags Ollama проходят через один manifest/blob adapter. Bundle содержит только provider-relative paths и импортируется в configured roots получателя, поэтому исходный checkout, имя пользователя и drive letter не сохраняются.

Import не переносит runtime binaries/settings, не перезаписывает отличающиеся существующие файлы и публикует Ollama manifest после blobs. Inspect/import report перечисляет runtime, которые должны быть локально подготовлены на получателе: Ollama, faster-whisper, Piper, а для whisper.cpp также CLI и Silero VAD. После успеха UI перечитывает обычные provider inventories.

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
