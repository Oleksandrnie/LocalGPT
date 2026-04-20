# Cleanup Notes

Текущее состояние после объединения:

- runtime работает как единый `LocalGPT` проект;
- модели разведены по feature-папкам внутри `models/`;
- LAN launcher нормализуется вокруг `start_localgpt_lan.*`;
- `LTrnsrb.*` пока оставлен как backward-compatible alias;
- `compare-branch/` остаётся внутри репозитория только как `read-only reference`;
- reference-папки внутри него нормализованы как `chat / asr / tts / ocr`.

Что ещё считается cleanup-задачей, а не текущим runtime:

- физическое удаление `compare-branch/` после parity-checklist;
- удаление legacy alias `LTrnsrb.*` после подтверждения нового launcher flow;
- дальнейший распил giant frontend/backend файлов на более мелкие feature-модули.
