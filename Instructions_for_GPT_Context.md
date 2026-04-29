# LocalGPT Runtime Context

Релевантные сущности unified runtime:

1. `chat message` — пользовательский или assistant message в текущей сессии.
2. `profile` — активный профиль с собственными настройками и историей.
3. `ASR transcript` — запись в истории `ASR Studio` или быстрый voice-to-input результат.
4. `TTS history item` — запись генерации в `app/data/tts/history`.
5. `OCR text` — извлечённый из изображения текст до вставки/отправки в чат.
6. `model artifact` — любой chat/asr/tts артефакт внутри `/models`.
7. `LAN runtime` — backend + Caddy + LAN URL для телефона.

Важно:

- `ASR Studio` и быстрый voice-to-input — разные UX-сценарии.
- `Voice Studio` не должна автоматически подставлять текст без явного действия пользователя.
- OCR v1 в этой очереди ограничен изображениями, без PDF.
- `compare-branch/` используется только как reference для переноса решений.
