# How To Use Tailscale Mode

Use this when the MacBook is not on the same Wi-Fi network as the iPhone, but both devices can join the same private Tailscale tailnet.

## Steps

1. Start LocalGPT on the MacBook.
2. Confirm the backend is running locally.
3. Sign in to Tailscale on the MacBook.
4. Sign in to Tailscale on the iPhone with the same tailnet.
5. Enable the LocalGPT Tailscale plugin in `Settings -> Plugins`.
6. Run this command manually on the MacBook:

```bash
tailscale serve --bg http://127.0.0.1:<LOCALGPT_PORT>
```

7. Open the Tailscale Serve URL from the iPhone browser.

## Requirements

- The MacBook stays awake and online.
- LocalGPT stays running on the MacBook.
- The iPhone stays connected to Tailscale.
- Tailscale Serve points at the active LocalGPT backend port.

## Security

```text
Do not expose LocalGPT directly to the public internet.
Do not enable Tailscale Funnel unless you fully understand the risk.
Preferred mode: Tailscale private tailnet only.
```

Do not use router port forwarding, public IP exposure, Cloudflare Tunnel, or Tailscale Funnel for the default LocalGPT remote access mode.
