# Локальная настройка проверок репозитория

В Git-клоне обычный setup LocalGPT предлагает настроить safeguards для разработчика. После подтверждения он устанавливает собственное окружение `.repo-safety-venv/`, недостающие инструменты безопасности и включает отслеживаемые Git hooks из `.githooks/`. Пути к другим репозиториям и машины в настройке не записываются. Если настройка запущена отдельно, выполните:

```sh
python3 scripts/setup_repo_safety.py install
```

Нужен Python 3.12 или новее. Скрипт создаёт локальную виртуальную среду, устанавливает закреплённую версию AI Repo Safety и задаёт `core.hooksPath=.githooks` только для этого клона.

## Установка сканеров

Проверки fail-closed и требуют Gitleaks и TruffleHog. Установите оба инструмента на каждой машине и убедитесь, что они доступны из обычного терминала:

- macOS с Homebrew: `brew install gitleaks trufflehog`.
- Windows: установите Gitleaks через WinGet (`winget install --id Gitleaks.Gitleaks -e`), TruffleHog — из официального релиза; добавьте оба исполняемых файла в пользовательский или системный `PATH`.
- Linux: установите оба инструмента из официальных релизов или пакетного менеджера дистрибутива и добавьте каталоги в `PATH`.

После изменения системного `PATH` перезапустите GitHub Desktop. На macOS hooks также проверяют обычные каталоги Homebrew и PATH login-shell, так что запуск Desktop из Finder не зависит от того, наследовал ли он интерактивный терминал. На Windows/Linux hook использует PATH процесса и PATH login-shell, если он задан.

Повторно проверьте установку:

```sh
python scripts/setup_repo_safety.py install
python scripts/setup_repo_safety.py gate --when commit
```

Перед push hook автоматически проверит добавленные пути, Gitleaks по диапазону `origin/dev..HEAD` и AI Repo Safety push gate. При отсутствии Python-модуля или сканера операция остановится. Никогда не обходите это через `--no-verify`.

Для TruffleHog hook передаёт в AI Repo Safety тот же target branch, который используется для path- и Gitleaks-проверки. Это не даёт внутреннему выбору `origin/main` просканировать постороннюю старую историю, если PR направляется в `dev`.
