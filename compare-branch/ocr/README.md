# OCR Reference

Эта папка хранит reference-снимок OCR v1 из unified `LocalGPT`.

Назначение:
- не используется runtime-кодом;
- нужна как reference-only база для будущего OCR mini-app и дальнейшего расширения;
- держится рядом с `compare-branch/chat`, `compare-branch/asr` и `compare-branch/tts`.

Состав:
- `app/routes/ocr.py` — текущий OCR route;
- `app/services/ocr.py` — текущий OCR service с `rus + ukr + eng` и auto-crop логикой.

Замысел на будущее:
- отдельная OCR Studio;
- история OCR-извлечений;
- более сильный pipeline для изображений/скриншотов;
- возможное расширение до PDF/OCR batch flow.
