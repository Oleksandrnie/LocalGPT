# Tailscale Remote Access Plugin

Official/internal metadata plugin for private Tailscale access to LocalGPT.

This folder is metadata and documentation only. LocalGPT reads `plugin.json` from this folder, but it does not import or execute code from `plugins/tailscale/`. The trusted implementation lives in backend-owned code under `backend/apps/plugins/`.

## Safety

- Do not expose LocalGPT directly to the public internet.
- Do not enable Tailscale Funnel unless you fully understand the risk.
- Preferred mode: Tailscale private tailnet only.
- This plugin never starts `tailscale serve` automatically.
- This plugin never opens router ports or public firewall rules.

## Manual Serve Command

Run this manually on the MacBook that runs LocalGPT:

```bash
tailscale serve --bg http://127.0.0.1:<LOCALGPT_PORT>
```

Replace `<LOCALGPT_PORT>` with the active LocalGPT backend port, usually `8000`.

## Docs

- [Remote access with Tailscale](docs/remote-access-tailscale.md)
- [How to use Tailscale mode](docs/how-to-use-tailscale-mode.md)

Official Tailscale references:

- [Tailscale Serve](https://tailscale.com/docs/features/tailscale-serve)
- [`tailscale serve` command](https://tailscale.com/docs/reference/tailscale-cli/serve)
