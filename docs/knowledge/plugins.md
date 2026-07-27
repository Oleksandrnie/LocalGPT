# Plugins

## Текущая модель

Plugin Registry v0 — metadata registry, а не система выполнения стороннего кода.

- Manifest: `plugins/<plugin-id>/plugin.json`.
- Registry: `backend/apps/plugins/registry.py`.
- API: `backend/apps/plugins/routes.py`.
- Trusted behavior: backend-owned handler, зарегистрированный по известному plugin id.
- Enabled state: локальный JSON state вне plugin manifest.

Runtime сканирует manifests, но не импортирует Python/JavaScript из `plugins/`.

## Manifest contract

Tailscale manifest показывает текущие поля:

- `id`, `name`, `type`, `version`;
- `enabled_by_default`;
- `description`;
- `permissions`;
- `dangerous_permissions`;
- `docs`.

Registry валидирует id/path и docs references. Некорректный manifest возвращается в списке как invalid вместо исполнения или silent skip.

## Trust

Trust задаётся backend allowlist/handler registry, а не содержимым manifest.

- unknown id — untrusted;
- untrusted plugin может иметь сохранённый enabled flag, но не становится `effective_enabled`;
- trusted plugin работает только через backend-owned handler;
- dangerous permissions отображаются UI и не дают автоматической capability.

## API

- `GET /plugins` — manifests, validation, trust, state, docs и handler status;
- `POST /plugins/{plugin_id}/enabled` — локальный enabled state;
- `GET /plugins/{plugin_id}/docs/{doc_path}` — безопасное чтение manifest-declared docs;
- `GET /plugins/network-addresses` — core LAN и trusted provider addresses.

Docs route нормализует путь и не должен позволять выйти из plugin directory.

## Tailscale handler

`backend/apps/plugins/tailscale.py`:

- проверяет наличие Tailscale CLI;
- читает `tailscale status --json` и `tailscale serve status --json`;
- определяет private-tailnet address/status;
- учитывает активный backend port из request scope/runtime/env;
- возвращает manual Serve command и copyable address metadata.

Handler не запускает `tailscale serve`, не включает Funnel, не меняет firewall/router и не открывает public ports.

Plugin-owned документация остаётся в:

- [`plugins/tailscale/README.md`](../../plugins/tailscale/README.md);
- [`plugins/tailscale/docs/remote-access-tailscale.md`](../../plugins/tailscale/docs/remote-access-tailscale.md);
- [`plugins/tailscale/docs/how-to-use-tailscale-mode.md`](../../plugins/tailscale/docs/how-to-use-tailscale-mode.md).

Эти пути перечислены в manifest и поэтому являются частью component contract.

## Lifecycle

1. scan manifest directories;
2. validate metadata/docs;
3. load local enabled state;
4. combine trust + enabled + handler availability into effective state;
5. expose status/UI controls;
6. invoke только конкретный backend-owned handler.

Hot reload arbitrary code отсутствует.

## Security boundaries

- manifests — данные, не код;
- default state disabled;
- trust нельзя self-declare;
- public exposure не является plugin capability;
- network addresses строит backend;
- UI не hardcode-ит Tailscale URL;
- runtime actions, которые меняют сеть, остаются manual.

## Не реализовано

- external plugin processes/IPC;
- marketplace, signing и update model;
- arbitrary plugin installation;
- hot reload executable code;
- миграция ASR/TTS/RAG/OCR/chat в plugins.

Эти пункты требуют отдельного security design и перечислены в [BACKLOG.md](../BACKLOG.md).
