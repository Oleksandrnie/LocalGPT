# Networking

## Режимы

| Режим | Backend bind | Внешний слой | Назначение |
| --- | --- | --- | --- |
| Local | `127.0.0.1:<port>` | нет | тот же компьютер |
| LAN | `127.0.0.1:<port>` | Caddy HTTPS на private LAN IP | устройства в одной локальной сети |

Прямой bind на `0.0.0.0` возможен через CLI/config, но launcher выводит предупреждение. Штатный LAN path не требует публичного backend bind.

## Local runtime

Default:

```bash
./start_localgpt.sh
```

или:

```bash
venv/bin/python run_localgpt.py --host 127.0.0.1 --port 8000
```

Обычные `start_localgpt.command`, `./start_localgpt.sh` и platform launchers запускают только локальный backend; LAN listener не включается автоматически. На macOS обычный launcher также останавливает управляемый LocalGPT Caddy listener, оставшийся от предыдущего LAN-сеанса. Для отдельной остановки используйте `stop_localgpt_lan.command` или `./stop_localgpt_lan.sh`. Launcher выбирает следующий свободный порт, если requested port занят. `--strict-port` вместо этого прекращает запуск. `--port-file` записывает фактически выбранный порт.

Health endpoint возвращает минимальные runtime metadata и доступные private access URLs без filesystem paths:

```bash
curl http://127.0.0.1:8000/health
```

## LAN через Caddy

На macOS доступ в локальной сети включается отдельным `start_localgpt_lan.command` или `./start_localgpt_lan.sh`. Они запускают `tools/LTrnsrb.sh` (legacy filename). Launcher:

- читает `LOCALGPT_PORT`/legacy backend port и `LAN_HTTPS_PORT`;
- определяет private LAN IP;
- запускает backend на localhost;
- генерирует runtime Caddyfile во временном каталоге;
- создаёт internal TLS listener на LAN IP и optional `.local` host;
- явно bind-ит listener только к найденному private IP и не создаёт отдельный HTTP redirect listener на `:80`;
- reverse-proxy-ит на фактический backend port;
- перезапускает Caddy при изменении generated config, LAN IP или фактического backend port, чтобы не сохранить stale upstream;
- хранит PID/log/port files в temporary runtime directory.

`Caddyfile.lan` в репозитории — localhost fallback/example; launcher создаёт актуальный config динамически.

Если Caddy не установлен или private LAN IP не обнаружен, launcher явно сообщает об этом и открывает только localhost UI.

Для автоматизированной диагностики можно задать `LOCALGPT_NO_BROWSER=1`: launcher выполнит тот же startup flow и напечатает URL, но не откроет вкладку браузера.

Первое устройство может потребовать доверия к Caddy local CA. Не публикуйте generated certificate/private key.

Когда LAN HTTPS listener отвечает, Settings → System → «Доступ с телефона» позволяет сохранить публичный `root.crt` Caddy на текущем компьютере для iPhone или Android. Файл отдаётся только через guarded `GET /network/caddy/root-ca` с `Cache-Control: no-store`; он не содержит private key. Браузер сохраняет файл в выбранную папку или стандартные downloads — затем пользователь передаёт его на устройство и вручную включает доверие. Если LAN URL недоступен, действия сохранения отключены.

## Host, port и CORS

Основные настройки:

- `LOCALGPT_HOST`, `LOCALGPT_PORT`;
- `LAN_HTTPS_PORT` (и поддерживаемые launcher aliases);
- `LOCALGPT_CORS_ALLOW_ORIGINS`;
- `LOCALGPT_CORS_ALLOW_ORIGIN_REGEX`.

Default CORS regex разрешает localhost, loopback, RFC1918 ranges и `.local` hosts. `allow_credentials` выключен. Same-origin static UI обычно не требует добавлять origins.

Не ставьте `*` без отдельного threat review.

## Security restrictions

- backend по умолчанию слушает localhost;
- Caddy завершает внешнее соединение и проксирует на localhost;
- обычный launcher остаётся local-only; LAN HTTPS включается отдельным явным entry point;
- приложение не предоставляет общую identity/authentication для LAN-клиентов; TLS защищает транспорт, но любой клиент с сетевым доступом может обращаться к незакрытым API, поэтому используйте только доверенную сеть;
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

### CORS error

Определите реальный Origin и добавьте только нужный origin/regex. Не маскируйте проблему открытием всего интернета.

### UI открывается, API нет

Проверьте reverse proxy upstream, фактический backend port, runtime logs и `/health` напрямую.

## Проверки

См. [TESTING.md](../TESTING.md), `tests/test_plugin_registry.py` и manual LAN matrix.
