# LocalGPT Unified Context

Текущий проект — единый runtime для:

- `chat`
- `asr`
- `tts`
- `ocr`
- `lan`

Базовые принципы:

1. Все модели и кэши живут только внутри `models/`.
2. `compare-branch/` — только reference, не runtime-источник.
3. `+ -> Транскрибировать` открывает `ASR Studio`.
4. `+ -> Озвучить` открывает `Voice Studio`.
5. `+ -> Файл` запускает OCR v1 для изображений.
6. LAN-launcher с понятным именем — `start_localgpt_lan.*`.
7. `LTrnsrb.*` остаётся только как legacy alias.

Ключевые каталоги:

- `app/routes/`
- `app/routers/`
- `app/services/`
- `app/data/`
- `web_ui/`
- `models/`

Feature-зоны:

- `chat`: профили, диалоги, сообщения, model settings, Ollama download flow
- `asr`: voice-to-input, файловая транскрибация, `ASR Studio`, transcript history
- `tts`: `Voice Studio`, Piper voices, audio history, speed variants
- `ocr`: image-to-text, OCR editor, insert/send to chat
- `lan`: Caddy, LAN URL, launcher flow, shutdown/runtime metadata

Документация и naming должны использовать `LocalGPT LAN` / `start_localgpt_lan.*` как основной путь.
