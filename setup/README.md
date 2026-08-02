# Первичная настройка LocalGPT

Эта папка содержит все entry points и внутреннюю реализацию первичной настройки LocalGPT:

- `setup_localgpt.command` — двойной клик или Terminal entry для macOS;
- `setup_localgpt.sh` — shell entry для Linux;
- `setup_localgpt.bat` — двойной клик или `cmd.exe` entry для Windows;
- `setup_localgpt.py` — общий interactive core для macOS, Linux и Windows;
- `setup_localgpt.ps1` — Windows PowerShell adapter.

Из корня проекта используйте один platform entry point:

- macOS — `./setup/setup_localgpt.command`;
- Linux — `./setup/setup_localgpt.sh`;
- Windows — `setup\setup_localgpt.bat`.

Setup всегда читает канонический `app/requirements.txt` и создаёт `venv/`, который затем использует `run_localgpt.py`. Окружение `.venv/`, созданное вручную, не подменяется и не удаляется.

На macOS setup также собирает native `models/whisper_cpp/bin/whisper-cli` и загружает небольшой Silero VAD runtime для отсечения тишины. Это не загружает GGML-модель или CoreML encoder: их по-прежнему добавляют отдельно в ASR Library.

Подробный dependency inventory и правила установки: [`docs/DEPENDENCIES.md`](../docs/DEPENDENCIES.md).
