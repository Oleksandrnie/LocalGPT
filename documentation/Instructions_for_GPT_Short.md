> Source: `Instructions_for_GPT_Short.md`
> This is a documentation-hub copy. Update the source document first, then refresh this copy.
# LocalGPT Short

Unified-проект сфокусирован на:

- локальном чате;
- `ASR Studio`;
- `Voice Studio`;
- OCR v1 для изображений;
- LAN-доступе с телефона.

Основа:

- `FastAPI`
- `WebUI`
- `Ollama`
- `whisper.cpp` by default, `faster-whisper` fallback
- `Piper`
- `Tesseract`

Storage:

- `models/ollama`
- `models/whisper`
- `models/whisper_cpp`
- `models/tts/piper`
- `models/hf_cache`
- `models/ctranslate2_cache`
- `app/data/tts`
- `app/db/localgpt.db`

Legacy `LTrnsrb` naming сохранён только как alias.
