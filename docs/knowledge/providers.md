# Providers

В LocalGPT нет одного универсального provider API. Provider-like границы разделены по назначению: chat/Ollama runtime, ASR backend и формальный TTS contract.

## Chat и Ollama

`backend/apps/chat/services/ollama_runtime.py` — низкоуровневый клиент локального Ollama:

- normal и streaming chat;
- model load/unload и active runners;
- `keep_alive`, `think` и Metal→CPU fallback;
- принудительная остановка зависших runners в ограниченных recovery flows.

`model_residency.py` управляет target-model policy отдельно от router model. Ручной и auto режимы могут использовать разные `keep_alive`; target limit предотвращает накопление тяжёлых моделей.

`model_router.py`:

- использует utility model `qwen3:0.6b`;
- принимает только известные intents;
- принудительно сопоставляет intent и разрешённую target model;
- корректирует явные code и простые RAG lookup запросы;
- использует fallback при invalid JSON или низкой confidence;
- не выбирает Local Calculator автоматически.

Model discovery и install state принадлежат `app/services/models.py`. Состояния различают configured, installed, active, downloading, partial и missing; наличие orphan partial blob не равно установленной runtime-модели.

## ASR backends

Конфигурация `WHISPER_BACKEND` принимает:

- `whisper_cpp` — явный whisper.cpp;
- `faster_whisper` — Python/CTranslate2;
- `auto` — whisper.cpp при готовом binary/model, иначе faster-whisper.

`backend/apps/asr/whisper.py` выбирает backend и нормализует общий результат. `whisper_cpp.py` владеет binary/model discovery, command execution и подготовкой путей. `downloads.py` управляет model preparation/update state.

Основные параметры находятся в `.env.example`: model, device, compute type, beam size, binary, threads, model path, FFmpeg и CoreML download policy.

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
