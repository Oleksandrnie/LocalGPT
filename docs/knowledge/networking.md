# Networking

## Режимы

| Режим | Backend bind | Внешний слой | Назначение |
| --- | --- | --- | --- |
| Local | `127.0.0.1:<port>` | нет | тот же компьютер |
| LAN | `0.0.0.0:<port>` | нет; прямой HTTP | устройства в доверенной локальной сети |

LAN-доступ включается только отдельным launcher-ом. Приложение не добавляет сетевую аутентификацию или TLS.

## Local runtime

Default:

```bash
./start_localgpt.sh
```

или:

```bash
venv/bin/python run_localgpt.py --host 127.0.0.1 --port 8000
```

Обычные `start_localgpt.command`, `./start_localgpt.sh` и `start_localgpt.bat` по умолчанию запускают backend только на localhost. Launcher выбирает следующий свободный порт, если requested port занят. `--strict-port` вместо этого прекращает запуск. `--port-file` записывает фактически выбранный порт.

Health endpoint возвращает минимальные runtime metadata без filesystem paths:

```bash
curl http://127.0.0.1:8000/health
```

## Прямой LAN-доступ

Запустите `./start_localgpt_lan.sh`; на macOS доступен `start_localgpt_lan.command`, на Windows — `start_localgpt_lan.bat`. Эти entry points передают общему launcher-у `--host 0.0.0.0`; обычный запуск остаётся loopback-only. Общий launcher выбирает свободный порт и выводит URL с обнаруженным private IPv4. Если IP определить не удалось, используйте адрес компьютера в той же Wi‑Fi сети вместе с напечатанным портом.

`0.0.0.0` слушает все сетевые интерфейсы, не только Wi‑Fi. LocalGPT не проверяет личность сетевых клиентов: любое устройство, которое может достичь порта, сможет читать и изменять данные приложения. Используйте этот режим только в доверенной частной сети; не настраивайте port forwarding и не открывайте порт в публичный Интернет. Связь идёт по HTTP без TLS. Некоторые браузерные функции, включая доступ к микрофону, могут требовать защищённый контекст и не работать по HTTP с локального IP.

Чтобы остановить LAN-сервер, завершите процесс в окне терминала (обычно `Ctrl+C`). Настройки firewall/router LocalGPT не меняет.

## Host, port и CORS

Основные настройки:

- `LOCALGPT_HOST`, `LOCALGPT_PORT`;
- `LOCALGPT_CORS_ALLOW_ORIGINS`;
- `LOCALGPT_CORS_ALLOW_ORIGIN_REGEX`.

Default CORS regex разрешает localhost, loopback, RFC1918 ranges и `.local` hosts. `allow_credentials` выключен. Same-origin static UI обычно не требует добавлять origins.

Не ставьте `*` без отдельного threat review.

## Security restrictions

- обычный launcher по умолчанию слушает localhost;
- отдельный LAN launcher явно включает bind на `0.0.0.0` и прямой HTTP;
- приложение не предоставляет общую identity/authentication или TLS для LAN-клиентов; любой клиент с сетевым доступом может читать и менять данные, поэтому используйте только доверенную сеть;
- unknown plugins не получают effective enable;
- network addresses формирует backend;
- LocalGPT не настраивает firewall/router автоматически;
- admin token по умолчанию пуст и не превращает runtime в public multi-user service.

LocalGPT рассчитан на локального владельца/доверенную private network, а не на публичный SaaS perimeter.

## Troubleshooting

### Порт занят

Запустите без `--strict-port` или выберите другой порт. Сверяйте URL с launcher output и `/health`.

### LAN URL отсутствует

- проверьте, что запущен `start_localgpt_lan` launcher;
- проверьте private IPv4 адрес компьютера и фактический порт из вывода launcher-а;
- убедитесь, что устройства находятся в одной сети и Wi‑Fi client isolation выключен;
- проверьте системный firewall и что он допускает соединение на этот порт.

### CORS error

Определите реальный Origin и добавьте только нужный origin/regex. Не маскируйте проблему открытием всего интернета.

### UI открывается, API нет

В прямом LAN режиме UI и API используют один адрес; проверьте runtime logs, фактический порт и `/health` на этом же host.

## Проверки

См. [TESTING.md](../TESTING.md), `tests/test_plugin_registry.py` и manual LAN matrix.
