# Plugin Architecture

This document describes the current LocalGPT Plugin Registry v0 architecture.

The current plugin system is intentionally small and conservative. It exists to expose trusted, backend-owned integration surfaces without turning `plugins/` into an executable extension runtime.

## Current Model

Plugins are discovered from:

```text
plugins/*/plugin.json
```

Those manifests are metadata only. LocalGPT may read and validate the JSON manifest, but it must not import Python, JavaScript, shell scripts, or any other executable code from `plugins/`.

The trusted implementation for a plugin id must live in backend-owned code, currently under:

```text
backend/apps/plugins/
```

For example, the official/internal Tailscale integration uses:

```text
plugins/tailscale/plugin.json
backend/apps/plugins/tailscale.py
```

The folder under `plugins/tailscale/` provides metadata and docs. The trusted handler is `backend/apps/plugins/tailscale.py`.

## Registry API

Current API surface:

```text
GET /plugins
POST /plugins/{plugin_id}/enabled
GET /plugins/network-addresses
```

`GET /plugins` returns detected plugin manifests, trusted/untrusted state, enabled state, docs availability, permissions, dangerous permissions, and trusted handler status when available.

`POST /plugins/{plugin_id}/enabled` stores local enabled/disabled state. Unknown or untrusted plugin ids cannot become effectively enabled.

`GET /plugins/network-addresses` returns copyable network address items from backend-owned providers only:

- core LAN provider;
- trusted plugin handlers, such as `tailscale`, only when trusted and enabled.

## Trust Rules

- `plugins/*/plugin.json` is metadata only.
- Unknown plugin ids are detected but untrusted.
- Untrusted plugins cannot be enabled.
- Plugins are disabled by default.
- Trusted plugin ids are allowlisted in backend-owned code.
- Trusted handlers must not execute code from `plugins/`.
- Trusted handlers should be narrow and explicit about what they can read or change.

## Manifest Fields

The current registry requires:

```text
id
name
type
version
enabled_by_default
description
permissions
dangerous_permissions
docs
```

The plugin id must match the folder name and use lowercase letters, digits, underscore, or hyphen.

## Enabled State

Enabled state is stored locally through app settings. A plugin is only effectively enabled when:

- the manifest is valid;
- the plugin id is trusted by backend-owned code;
- the user has enabled it.

This prevents a random folder under `plugins/` from gaining runtime privileges.

## Network Address Provider Contract

Network address items are plain data returned by backend-owned providers:

```json
{
  "id": "tailscale",
  "provider_id": "tailscale",
  "label": "Tailscale",
  "url": "https://example.tailnet.ts.net/ui/gui_html.html",
  "detail": "Private tailnet via Tailscale Serve.",
  "trusted": true,
  "copyable": true,
  "priority": 20,
  "security_note": "Private tailnet only."
}
```

The frontend must not synthesize Tailscale URLs. It should copy only backend-provided URLs that are non-empty and copyable.

Fast path behavior:

- zero addresses: disable copy action or show an error/warning;
- one address: left click copies immediately;
- multiple addresses: left click opens a menu;
- no right-click-only address selection.

## Tailscale Handler

The `tailscale` handler may perform read-only checks:

- `tailscale` CLI presence;
- `tailscale status --json`;
- `tailscale serve status --json`;
- generated manual command text.

The handler must not:

- run `tailscale serve` automatically;
- run or enable Tailscale Funnel;
- open public ports;
- change firewall/router settings;
- create LaunchAgents;
- execute code from `plugins/`.

Manual setup remains explicit:

```bash
tailscale serve --bg http://127.0.0.1:<LOCALGPT_PORT>
```

## Not Implemented

The current architecture does not implement:

- marketplace installation;
- plugin downloads from the internet;
- hot reload of plugin code;
- external plugin process API;
- Caddy plugin;
- migration of ASR/TTS/RAG into plugins.

Those ideas belong in backlog planning, not in Plugin Registry v0 runtime behavior.
