# Remote Access With Tailscale

This is the durable LocalGPT reference for secure remote access through Tailscale.

Sources:

- Tailscale Serve docs: https://tailscale.com/docs/features/tailscale-serve
- `tailscale serve` CLI reference: https://tailscale.com/docs/reference/tailscale-cli/serve
- Tailscale Funnel docs: https://tailscale.com/docs/features/tailscale-funnel

## Security Rule

```text
Do not expose LocalGPT directly to the public internet.
Do not enable Tailscale Funnel unless you fully understand the risk.
Preferred mode: Tailscale private tailnet only.
```

Tailscale mode is meant for a private tailnet only. It does not require router port forwarding, a public IP address, Cloudflare Tunnel, or Tailscale Funnel.

## Runtime Model

- The MacBook runs LocalGPT, Ollama/model runtime, ASR, TTS, OCR, and RAG.
- The iPhone is only a browser client.
- The MacBook must be awake, online, running LocalGPT, and logged into the same Tailscale tailnet as the iPhone.
- The iPhone must have Tailscale connected before opening the LocalGPT URL.
- LocalGPT backend stays bound to localhost: `127.0.0.1:<LOCALGPT_PORT>`.
- Tailscale Serve proxies private tailnet traffic to the localhost backend.

## What The Plugin Provides

The official/internal plugin id is `tailscale`.

The manifest and plugin-local docs live under `plugins/tailscale/`, but LocalGPT treats that folder as metadata only. Backend-owned code under `backend/apps/plugins/` is the only trusted implementation path.

The trusted handler may do read-only checks:

- whether the `tailscale` CLI exists;
- `tailscale status --json`;
- `tailscale serve status --json`;
- the generated manual Serve command for the active LocalGPT port.

The handler must not:

- execute code from `plugins/`;
- run `tailscale serve` automatically;
- run `tailscale funnel`;
- open public ports;
- change router, firewall, LaunchAgent, or system network settings.

## Manual Serve Command

Run this manually on the MacBook after LocalGPT is already running:

```bash
tailscale serve --bg http://127.0.0.1:<LOCALGPT_PORT>
```

Replace `<LOCALGPT_PORT>` with the active backend port. In the normal local launch this is usually `8000`; if the launcher selected a nearby free port, use that actual port.

Do not replace this with `tailscale funnel`. Funnel is for public internet exposure and is not the default or recommended LocalGPT remote-access mode.

## Access Control Notes

Tailscale Serve routes traffic from devices in the tailnet to a local service. Tailscale access control rules still apply, so tailnet policy can restrict which users and devices can reach the served LocalGPT URL.

Serve traffic can include Tailscale identity headers for tailnet requests. LocalGPT does not currently treat those headers as an authentication layer; the safe default remains private tailnet-only exposure with trusted devices and users.

## Expected Address

When Tailscale Serve is active for LocalGPT, the usable URL is expected to look like:

```text
https://<macbook-tailnet-name>.<tailnet>.ts.net/ui/gui_html.html
```

The exact hostname comes from Tailscale. The frontend must not hardcode this URL; it should use backend-provided network address items from trusted handlers.

## Troubleshooting

Check the MacBook:

```bash
tailscale status
tailscale serve status
curl -fsS http://127.0.0.1:<LOCALGPT_PORT>/health
```

If the iPhone cannot open LocalGPT:

- confirm the MacBook is awake and LocalGPT is running;
- confirm both devices are in the same tailnet;
- confirm Tailscale is connected on the iPhone;
- confirm Tailscale Serve points to the active LocalGPT backend port;
- confirm the plugin is enabled in `Settings -> Plugins`;
- do not troubleshoot by opening public router ports or enabling Funnel.
