# Remote Access With Tailscale

This plugin is for private tailnet access only. It lets another device in your Tailscale network open the LocalGPT UI running on the MacBook.

Mandatory security rules:

```text
Do not expose LocalGPT directly to the public internet.
Do not enable Tailscale Funnel unless you fully understand the risk.
Preferred mode: Tailscale private tailnet only.
```

## What Runs Where

- The MacBook runs LocalGPT, Ollama/model runtime, ASR, TTS, OCR, and RAG.
- The iPhone or another device is only a browser client.
- The MacBook must be awake, online, running LocalGPT, and logged into the same tailnet.
- The client device must also be logged into the same tailnet.

## What This Plugin Does

- Reads `plugins/tailscale/plugin.json` as metadata.
- Uses a trusted backend-owned handler for plugin id `tailscale`.
- Performs read-only checks for `tailscale status --json` and `tailscale serve status --json` when the CLI is available.
- Shows the manual command needed to publish LocalGPT inside the private tailnet.

## What This Plugin Does Not Do

- It does not run `tailscale serve`.
- It does not enable Tailscale Funnel.
- It does not open public ports.
- It does not configure router port forwarding.
- It does not execute code from `plugins/`.

## Manual Command

Run this manually on the MacBook:

```bash
tailscale serve --bg http://127.0.0.1:<LOCALGPT_PORT>
```

Use the active LocalGPT backend port. In a default local launch this is usually `8000`.

## Notes

Tailscale Serve shares a local service inside the private tailnet. Tailscale Funnel is different: Funnel exposes a service to the public internet. LocalGPT recommends Serve only, not Funnel.

References:

- [Tailscale Serve](https://tailscale.com/docs/features/tailscale-serve)
- [`tailscale serve` command](https://tailscale.com/docs/reference/tailscale-cli/serve)
