# Plugins

## Текущая модель

Plugin Registry v0 — metadata registry, а не система выполнения стороннего кода.

- Manifest path: `plugins/<plugin-id>/plugin.json`.
- Registry: `backend/apps/plugins/registry.py`.
- API: `backend/apps/plugins/routes.py`.
- Local enabled state хранится вне manifest.
- Сейчас официальные plugin manifests и trusted plugin handlers не поставляются.

Runtime может сканировать manifests, но не импортирует Python/JavaScript из `plugins/`.

## Manifest contract

Manifest описывает metadata и ссылки на документацию:

- `id`, `name`, `type`, `version`;
- `enabled_by_default`;
- `description`;
- `permissions` и `dangerous_permissions`;
- `docs`.

Registry валидирует id/path и docs references. Некорректный manifest возвращается в списке как invalid вместо исполнения или silent skip.

## Trust

Trust задаётся backend allowlist/handler registry, а не содержимым manifest.

- unknown id — untrusted;
- untrusted plugin может иметь сохранённый enabled flag, но не становится `effective_enabled`;
- trusted plugin, если будет зарегистрирован в будущем, может работать только через backend-owned handler;
- dangerous permissions отображаются UI и не дают автоматической capability.

В текущей поставке trusted allowlist и handler/address maps пусты.

## API

- `GET /plugins` — manifests, validation, trust, state, docs и handler status;
- `POST /plugins/{plugin_id}/enabled` — локальный enabled state;
- `GET /plugins/{plugin_id}/docs/{doc_path}` — безопасное чтение manifest-declared docs;
- `GET /plugins/network-addresses` — core LAN/provider addresses, если они доступны.

Docs route нормализует путь и не должен позволять выйти из plugin directory.

## Lifecycle

1. scan manifest directories;
2. validate metadata/docs;
3. load local enabled state;
4. combine trust + enabled + handler availability into effective state;
5. expose status/UI controls;
6. invoke только конкретный backend-owned handler, когда он зарегистрирован.

Hot reload arbitrary code отсутствует.

## Security boundaries

- manifests — данные, не код;
- default state disabled;
- trust нельзя self-declare;
- public exposure не является plugin capability;
- network addresses строит backend;
- runtime actions, которые меняют систему или сеть, требуют отдельного backend-owned поведения.

## Не реализовано

- external plugin processes/IPC;
- marketplace, signing и update model;
- arbitrary plugin installation;
- hot reload executable code;
- миграция ASR/TTS/RAG/OCR/chat в plugins.

Любой переход от metadata-only manifests к запуску внешнего кода требует отдельного security design.
