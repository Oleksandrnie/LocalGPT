# TTS Runtime Context

Для текущей ветки релевантны только TTS-сущности:

1. `text` — исходный текст для синтеза.
2. `voice_id` — выбранный локальный Piper-голос.
3. `speed` — пост-обработка `1.0x`-`2.0x`.
4. `history item` — запись генерации в `app/data/tts/history`.
5. `output wav` — файл в `app/data/tts/output`.

Legacy speech-to-text flow здесь не используется.
