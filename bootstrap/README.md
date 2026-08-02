# Bootstrap internals

Эта папка содержит внутреннюю реализацию первого запуска LocalGPT:

- `bootstrap_localgpt.py` — общий interactive core для macOS, Linux и Windows;
- `bootstrap_localgpt.ps1` — Windows PowerShell adapter.

Обычно эти файлы не запускаются напрямую. В корне проекта используйте один platform entry point:

- macOS — `bootstrap_localgpt.command`;
- Linux — `bootstrap_localgpt.sh`;
- Windows — `bootstrap_localgpt.bat`.

Подробный dependency inventory и правила установки: [`docs/DEPENDENCIES.md`](../docs/DEPENDENCIES.md).
