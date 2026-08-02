# Networking

## Режимы

| Режим | Backend bind | Внешний слой | Назначение |
| --- | --- | --- | --- |
| Local | `127.0.0.1:<port>` | нет | тот же компьютер |
| LAN | `127.0.0.1:<port>` | Caddy HTTPS на private LAN IP | устройства в одной локальной сети |
| Tailscale | `127.0.0.1:<port>` | ручной Tailscale Serve | устройства в private tailnet |

Прямой bind на `0.0.0.0` возможен через CLI/config, но launcher выводит предупреждение. Штатные LAN/Tailscale paths не требуют публичного backend bind.

## Local runtime

Default:

```bash
./start_localgpt.sh
```

или:

```bash
venv/bin/python run_localgpt.py --host 127.0.0.1 --port 8000
```

Launcher выбирает следующий свободный порт, если requested port занят. `--strict-port` вместо этого прекращает запуск. `--port-file` записывает фактически выбранный порт.

Health endpoint возвращает access URL, LAN URL и основные runtime/model paths:

```bash
curl http://127.0.0.1:8000/health
```

## LAN через Caddy

На macOS обычный `start_localgpt.command` или `./start_localgpt.sh` без аргументов автоматически вызывает `tools/LTrnsrb.sh` (legacy filename); `start_localgpt_lan.command` остаётся compatibility alias. Launcher:

- читает `LOCALGPT_PORT`/legacy backend port и `LAN_HTTPS_PORT`;
- определяет private LAN IP;
- запускает backend на localhost;
- генерирует runtime Caddyfile во временном каталоге;
- создаёт internal TLS listener на LAN IP и optional `.local` host;
- reverse-proxy-ит на фактический backend port;
- хранит PID/log/port files в temporary runtime directory.

`Caddyfile.lan` в репозитории — localhost fallback/example; launcher создаёт актуальный config динамически.

Если Caddy не установлен или private LAN IP не обнаружен, launcher явно сообщает об этом и открывает только localhost UI. Явные аргументы macOS launchers сохраняют direct local launch для диагностики.

Первое устройство может потребовать доверия к Caddy local CA. Не публикуйте generated certificate/private key.

Когда LAN HTTPS listener отвечает, Settings → System → «Доступ с телефона» позволяет сохранить публичный `root.crt` Caddy на текущем компьютере для iPhone или Android. Файл отдаётся только через guarded `GET /network/caddy/root-ca` с `Cache-Control: no-store`; он не содержит private key. Браузер сохраняет файл в выбранную папку или стандартные downloads — затем пользователь передаёт его на устройство и вручную включает доверие. Если LAN URL недоступен, действия сохранения отключены.

## Tailscale private tailnet

1. Запустите LocalGPT локально.
2. Подключите Mac и client device к одному tailnet.
3. Включите trusted Tailscale plugin в Settings.
4. Выполните вручную:

   ```bash
   tailscale serve --bg http://127.0.0.1:<LOCALGPT_PORT>
   ```

5. Откройте Serve URL с client device.

Backend handler только читает status и показывает команду/адрес. Он не запускает Serve. Полная инструкция: [`plugins/tailscale/README.md`](../../plugins/tailscale/README.md).

Не используйте Funnel, router port forwarding, public IP exposure или public tunnel как default LocalGPT access.

## Host, port и CORS

Основные настройки:

- `LOCALGPT_HOST`, `LOCALGPT_PORT`;
- `LAN_HTTPS_PORT` (и поддерживаемые launcher aliases);
- `LOCALGPT_CORS_ALLOW_ORIGINS`;
- `LOCALGPT_CORS_ALLOW_ORIGIN_REGEX`;
- `LOCALGPT_REMOTE_ACCESS`, `LOCALGPT_REMOTE_ACCESS_MODE`.

Default CORS regex разрешает localhost, loopback, RFC1918 ranges, Tailscale CGNAT range и `.local` hosts. `allow_credentials` выключен. Same-origin static UI обычно не требует добавлять origins.

Не ставьте `*` без отдельного threat review.

## Security restrictions

- backend по умолчанию слушает localhost;
- Caddy/Tailscale terminate внешнее соединение и проксируют на localhost;
- Tailscale plugin metadata не исполняется;
- unknown plugins не получают effective enable;
- network addresses формирует backend;
- LocalGPT не настраивает firewall/router автоматически;
- admin token по умолчанию пуст и не превращает runtime в public multi-user service.

LocalGPT рассчитан на локального владельца/доверенную private network, а не на публичный SaaS perimeter.

## Troubleshooting

### Порт занят

Запустите без `--strict-port` или выберите другой порт. Сверяйте URL с launcher output и `/health`.

### LAN URL отсутствует

- проверьте private IP;
- Caddy process/listener;
- `LAN_HTTPS_PORT`;
- certificate trust;
- что backend health доступен на localhost.

### Tailscale адрес отсутствует

- plugin trusted и enabled;
- `tailscale status --json` успешен;
- Serve направлен на активный backend port;
- оба устройства в одном tailnet;
- Mac не спит.

### CORS error

Определите реальный Origin и добавьте только нужный origin/regex. Не маскируйте проблему открытием всего интернета.

### UI открывается, API нет

Проверьте reverse proxy upstream, фактический backend port, runtime logs и `/health` напрямую.

## Проверки

См. [TESTING.md](../TESTING.md), `tests/test_plugin_registry.py` и manual LAN/Tailscale matrix.
