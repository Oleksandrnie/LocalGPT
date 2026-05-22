# Tailscale Plugin + Secure Remote Access Plan

This is a temporary working plan for the current task. Keep it updated before commits and before any context/token compaction.

Delete this file after the Tailscale Plugin + Secure Remote Access Docs task is complete.

## Task Goal

Add secure remote access through Tailscale as an official/internal plugin with a trusted backend handler.

Tailscale must not become hardcoded core runtime behavior, and LocalGPT must not execute arbitrary code from `plugins/`.

## Original Task Snapshot

Task name:

```text
Tailscale Plugin + Secure Remote Access Docs
```

Core requirements from the original request:

- Add secure remote access through Tailscale as an official/internal plugin, not as hardcoded core runtime.
- Add minimal Plugin Registry v0.
- Add `Settings -> Plugins`.
- Add Tailscale plugin manifest/docs under `plugins/tailscale/`.
- Implement a trusted backend handler for the trusted plugin id `tailscale`.
- Do not execute arbitrary code from `plugins/`.
- Store plugin enabled/disabled state.
- Show trusted vs untrusted plugins.
- Keep plugins disabled by default.
- Do not automatically run shell commands.
- Do not automatically enable `tailscale serve`.
- Do not automatically enable Tailscale Funnel.
- Do not automatically expose public ports.
- Add network address provider API so frontend does not hardcode Tailscale URLs.
- Preserve LAN copy fast path:
  - one address -> left click copies immediately;
  - multiple addresses -> left click opens a menu;
  - no right-click-only address selection.
- Add Tailscale technical documentation and user-facing instruction.
- Add plugin architecture documentation.
- Add backlog documentation with Caddy plugin and external plugin process API as future ideas only.
- Update documentation hub without recreating it.
- Use source-first rule for copied hub docs.
- Keep LAN runtime untouched unless a new regression is found.

Out of scope from the original request:

- Caddy plugin implementation.
- External plugin process API implementation.
- Marketplace.
- Installing plugins from the internet.
- Hot reload of arbitrary plugin code.
- Migrating ASR/TTS/RAG into plugins.
- Repairing LAN remote without a newly found regression.

## Current Stop Point

We are stopped after Stage 3.

Last completed work:

- Commit `8880ba7 Polish RAG topbar UI`.
- Stage 2 - Plugin Registry v0 backend is implemented.
- Stage 3 - Settings -> Plugins UI is implemented.
- This temporary plan file and its links in `documentation/README.md` and `documentation/map.md` are tracking changes for this task.
- Stage 2/3 changes are being prepared as a checkpoint commit.

Next exact implementation step:

```text
Stage 4 - Tailscale Official/Internal Plugin
```

Start there by adding the Tailscale manifest/docs skeleton and trusted backend handler. Do not automatically run `tailscale serve`.

## Branch

Current branch:

```text
tailscale-remote-access
```

Do not create a new branch for this task.

## Already Done Before This Task

- LAN/local remote runtime was fixed and confirmed by the user on a phone.
- LocalGPT backend remains bound to `127.0.0.1:<LOCALGPT_PORT>` by default.
- Caddy reverse proxy works for LAN access through `https://<lan-ip>:<LAN_HTTPS_PORT>`.
- Caddy runs through macOS user LaunchAgent `local.localgpt.caddy`.
- LAN URL is only exposed by `/health` when the LAN HTTPS listener is actually reachable.
- CORS default is no longer `*`; it allows local/private origins including Tailscale CGNAT `100.64.0.0/10`.
- Runtime env fields exist:
  - `LOCALGPT_HOST`
  - `LOCALGPT_PORT`
  - `LOCALGPT_REMOTE_ACCESS`
  - `LOCALGPT_REMOTE_ACCESS_MODE`
  - `LOCALGPT_CORS_ALLOW_ORIGINS`
  - `LOCALGPT_CORS_ALLOW_ORIGIN_REGEX`
- `documentation/` hub exists with:
  - `documentation/README.md`
  - `documentation/map.md`
  - copied source docs with `Source:` notes.
- RAG topbar UI polish was committed separately in `8880ba7 Polish RAG topbar UI`.

## Done From This Task So Far

- Created this temporary tracking plan:
  - `documentation/tailscale-plugin-plan.md`
- Linked it from:
  - `documentation/README.md`
  - `documentation/map.md`
- Marked it as temporary and scheduled it for deletion at task completion.
- Added Plugin Registry v0 backend:
  - `plugins/.gitkeep`
  - `plugins/README.md`
  - `backend/apps/plugins/registry.py`
  - `backend/apps/plugins/routes.py`
  - `backend/apps/plugins/__init__.py`
- Added registry API routes:
  - `GET /plugins`
  - `POST /plugins/{plugin_id}/enabled`
  - `GET /plugins/network-addresses`
- Added app setting helpers in `app/db.py` for persistent plugin enabled state.
- Connected plugin routes in `backend/server.py`.
- Added `tests/test_plugin_registry.py`.
- Added Settings -> Plugins UI:
  - settings tab `Plugins`;
  - plugin registry summary;
  - plugin list, empty state, invalid manifest cards;
  - trusted/untrusted status;
  - permissions and dangerous permissions display;
  - enable/disable control wired to the registry API.

Tailscale plugin, network address menu, and Tailscale docs have not been implemented yet.

## Not Yet Done

- Tailscale plugin manifest/docs do not exist yet.
- Tailscale trusted handler does not exist yet.
- Network address copy menu for LAN/Tailscale choices does not exist yet.
- Tailscale technical and user-facing documentation does not exist yet.
- `documentation/plugin-architecture.md` does not exist yet.
- `documentation/backlog.md` does not exist yet.

## Safety Rules

- Do not re-fix LAN remote unless a new regression is found.
- Do not recreate the documentation hub.
- Do not execute Python/JS/shell code from `plugins/`.
- A plugin folder with `plugin.json` is metadata only unless a trusted backend handler exists.
- Unknown plugins may be shown as detected/untrusted, but must not execute.
- Plugins are disabled by default.
- Do not enable Tailscale Serve automatically.
- Do not enable Tailscale Funnel automatically.
- Do not open public ports automatically.
- Do not implement Caddy plugin in this task.
- Do not implement external plugin process API in this task.
- Do not migrate ASR/TTS/RAG into plugins in this task.

## Planned Stages

### Stage 0 - Current-State Sync

Status: done.

- Confirm branch.
- Confirm documentation hub exists.
- Confirm LAN runtime already works and should not be repaired again.
- Confirm current tree is clean after UI/RAG commit.

### Stage 1 - Minimal Sanity Check

Status: done.

Purpose: ensure plugin work starts from a stable baseline without repeating LAN repair.

Actions:

- Check `git status --short`.
- Optionally check that existing backend import/syntax is valid.
- Do not change LAN launcher/Caddy unless a regression is found.

### Stage 2 - Plugin Registry v0 Backend

Status: done.

Scope:

- Add `plugins/` skeleton:
  - `plugins/.gitkeep`
  - `plugins/README.md`
- Add trusted backend plugin layer, preferably under `backend/apps/plugins/`.
- Scan `plugins/*/plugin.json`.
- Validate required manifest fields.
- Ignore or mark invalid plugins without breaking core runtime.
- Store enabled/disabled state locally.
- Expose backend API for listing and toggling plugins.
- Distinguish trusted vs unknown plugin ids.
- Do not import/execute code from plugin folders.

Suggested API shape:

```text
GET /plugins
POST /plugins/{plugin_id}/enabled
GET /plugins/network-addresses
```

The exact path can be adapted to existing backend conventions.

### Stage 3 - Settings -> Plugins UI

Status: done.

Scope:

- Add Settings tab: `Plugins`.
- Show plugin list, status, trusted/untrusted state, docs, permissions, dangerous permissions.
- Add enable/disable control.
- Show empty state if no plugins are installed.
- Use existing settings UI/button/toggle patterns.
- Do not introduce native visible `<select>`.

### Stage 4 - Tailscale Official/Internal Plugin

Status: pending.

Scope:

- Add:
  - `plugins/tailscale/plugin.json`
  - `plugins/tailscale/README.md`
  - `plugins/tailscale/docs/remote-access-tailscale.md`
  - `plugins/tailscale/docs/how-to-use-tailscale-mode.md`
- Add trusted handler for `tailscale` in backend-owned code.
- Handler may safely read:
  - metadata
  - enabled state
  - security warnings
  - docs links
  - `tailscale` CLI presence
  - `tailscale status`
  - `tailscale serve status`
- Handler may provide manual command text:

```bash
tailscale serve --bg http://127.0.0.1:<LOCALGPT_PORT>
```

Forbidden in this stage:

- Automatically running `tailscale serve`.
- Automatically changing firewall/network settings.
- Automatically creating LaunchAgents.
- Automatically enabling Funnel.
- Opening public access.

### Stage 4b - Network Address Copy Menu

Status: pending.

Scope:

- Keep existing fast path:
  - 0 addresses: disabled/error toast.
  - 1 address: left click copies immediately.
  - 2+ addresses: left click opens a menu.
- Do not use right click for LAN/Tailscale choice.
- Address items must come from backend/trusted handlers, not hardcoded frontend logic.
- Show LAN address when available.
- Show Tailscale address only when trusted/enabled and available.
- Do not copy placeholders or dead addresses.

### Stage 5 - Tailscale Documentation

Status: pending.

Add primary docs:

- `documentation/remote-access-tailscale.md`
- `documentation/how-to-use-tailscale-mode.md`

Must include:

- Private tailnet only.
- No router port forwarding.
- No public IP requirement.
- No Cloudflare Tunnel requirement.
- No Tailscale Funnel as default/recommended mode.
- MacBook runs LocalGPT/model runtime; iPhone is only a client.
- MacBook must be awake, online, running LocalGPT, and logged into the same tailnet.

Mandatory security statements:

```text
Do not expose LocalGPT directly to the public internet.
Do not enable Tailscale Funnel unless you fully understand the risk.
Preferred mode: Tailscale private tailnet only.
```

### Stage 6 - Documentation Hub Updates

Status: pending.

Add:

- `documentation/plugin-architecture.md`
- `documentation/backlog.md`

Update:

- `documentation/README.md`
- `documentation/map.md`

Backlog must include:

- Caddy official/internal plugin as future stage.
- External Plugin Process API as future idea, not current implementation.

### Stage 7 - Source Docs, Hub Refresh, Checks

Status: pending.

Update source-first:

- root `README.md`
- `TECHNICAL_README.md`
- `backend/README.md` if backend plugin API/contracts are added.
- `docs/ui-components.md` if Settings -> Plugins UI conventions are added.

Then refresh hub copies:

- `documentation/README.project.md`
- `documentation/TECHNICAL_README.md`
- `documentation/README.backend_structure.md`
- `documentation/ui-components.md`

Run available checks:

```bash
venv/bin/python -m py_compile ...
node --check web_ui/js/app.js
python -m unittest ...  # if appropriate for touched backend areas
```

Manual checks to report:

- Core UI still loads.
- LAN fast path is not broken.
- Plugins tab shows Tailscale.
- Unknown plugin is detected but untrusted.
- Enabled state persists.
- No arbitrary plugin code is executed.
- Tailscale docs do not recommend public exposure or Funnel by default.

## Commit Strategy

Use small commits by stage:

1. Plugin Registry v0 backend.
2. Settings -> Plugins UI.
3. Tailscale plugin trusted handler and manifest.
4. Network address copy menu.
5. Tailscale/plugin docs and hub updates.

If a stage is too large, split it further.

## Continuation Prompt

Use this prompt to continue after context loss or compaction:

```text
Continue the LocalGPT task "Tailscale Plugin + Secure Remote Access Docs" on branch `tailscale-remote-access`.

First read `documentation/tailscale-plugin-plan.md`. It is a temporary working file and must be deleted after the whole task is complete.

Current status:
- LAN remote was already fixed earlier; do not repair LAN/Caddy unless a new regression is found.
- Documentation hub already exists; do not recreate it.
- Stage 2 is done: Plugin Registry v0 backend exists under `backend/apps/plugins/`, with `GET /plugins`, `POST /plugins/{plugin_id}/enabled`, and `GET /plugins/network-addresses`.
- Stage 3 is done: Settings -> Plugins UI exists and consumes the registry API.
- The registry reads `plugins/*/plugin.json` as metadata only. It must not import or execute code from `plugins/`.
- Unknown plugins are detected but untrusted and cannot be enabled.
- Plugins are disabled by default.
- Tailscale plugin, network address menu, and Tailscale docs are not done yet.

Next exact step:
Stage 4 - Tailscale official/internal plugin.

Implement:
- `plugins/tailscale/plugin.json`
- `plugins/tailscale/README.md`
- `plugins/tailscale/docs/remote-access-tailscale.md`
- `plugins/tailscale/docs/how-to-use-tailscale-mode.md`
- trusted backend handler for plugin id `tailscale`, in backend-owned code, not inside `plugins/tailscale/`
- read-only checks for tailscale CLI/status/serve status if safe
- security warnings and manual `tailscale serve --bg http://127.0.0.1:<LOCALGPT_PORT>` command text

Do not:
- run `tailscale serve` automatically
- enable Tailscale Funnel
- open public ports
- execute arbitrary plugin code
- implement Caddy plugin or external plugin process API
- migrate ASR/TTS/RAG to plugins

After Stage 4, continue with Stage 4b network address copy menu, then Stage 5 docs, Stage 6 hub docs/backlog/plugin architecture, and Stage 7 source docs/checks.
```

## Cleanup At Task Completion

When all task stages are complete:

- Delete this temporary file.
- Remove its links from:
  - `documentation/README.md`
  - `documentation/map.md`
- Ensure the final durable docs are:
  - `documentation/plugin-architecture.md`
  - `documentation/backlog.md`
  - `documentation/remote-access-tailscale.md`
  - `documentation/how-to-use-tailscale-mode.md`
  - updated source docs and refreshed hub copies.

## Handoff Checklist Before Context Compaction

Trigger phrase:

```text
давай подготовимся к переносу в другой чат
```

When the user says this phrase, do the handoff routine:

- update this temporary file with the latest completed stage, commit hash, checks, open changes, blockers, and next exact step;
- commit the handoff update if there are file changes;
- return two continuation prompts in chat:
  - Russian prompt for the user;
  - English prompt for Codex.

Before tokens run low, update this section with:

- Last completed stage.
- Last commit hash.
- Files changed but not committed.
- Tests/checks already run.
- Next exact step.
- Any risks or blockers.

Current handoff:

- Last completed task before this plan: RAG UI polish commit `8880ba7`.
- Last completed Tailscale Plugin stage: Stage 3 - Settings -> Plugins UI.
- Current task next step: Stage 4 - Tailscale Official/Internal Plugin.
- Working tree at latest update: contains Stage 2 backend changes, Stage 3 UI changes, and temporary plan updates ready for a checkpoint commit.
- Checks already run:
  - `venv/bin/python -m py_compile app/db.py backend/server.py backend/apps/plugins/__init__.py backend/apps/plugins/registry.py backend/apps/plugins/routes.py tests/test_plugin_registry.py`
  - `venv/bin/python -m unittest tests.test_plugin_registry`
  - TestClient smoke for `GET /plugins` and `GET /plugins/network-addresses`
  - `node --check web_ui/js/app.js`
- Known risk: future UI/docs edits must preserve source-first hub copy rule.
