# Setup internals

Эта папка содержит внутреннюю реализацию первичной настройки LocalGPT:

- `setup_localgpt.py` — общий interactive core для macOS, Linux и Windows;
- `setup_localgpt.ps1` — Windows PowerShell adapter.

Обычно эти файлы не запускаются напрямую. В корне проекта используйте один platform entry point:

- macOS — `setup_localgpt.command`;
- Linux — `setup_localgpt.sh`;
- Windows — `setup_localgpt.bat`.

Подробный dependency inventory и правила установки: [`docs/DEPENDENCIES.md`](../docs/DEPENDENCIES.md).
