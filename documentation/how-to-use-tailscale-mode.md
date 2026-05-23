# How To Use Tailscale Mode

Use Tailscale mode when the iPhone should open LocalGPT through a private tailnet instead of the same Wi-Fi LAN.

## Before You Start

```text
Do not expose LocalGPT directly to the public internet.
Do not enable Tailscale Funnel unless you fully understand the risk.
Preferred mode: Tailscale private tailnet only.
```

You do not need router port forwarding, a public IP address, Cloudflare Tunnel, or Tailscale Funnel.

## Devices

- MacBook: runs LocalGPT and the local model runtime.
- iPhone: browser client only.

The MacBook must stay awake, online, running LocalGPT, and logged into the same Tailscale tailnet as the iPhone.

## Setup

1. Install and sign in to Tailscale on the MacBook.
2. Install and sign in to Tailscale on the iPhone.
3. Confirm both devices appear in the same tailnet.
4. Start LocalGPT on the MacBook.
5. Open `Settings -> Plugins`.
6. Enable `Tailscale Remote Access`.
7. Find the active LocalGPT backend port. The default is usually `8000`.
8. Run this manually on the MacBook:

```bash
tailscale serve --bg http://127.0.0.1:<LOCALGPT_PORT>
```

Replace `<LOCALGPT_PORT>` with the actual active port.

## Open From iPhone

After Tailscale Serve is active, open the Serve URL in Safari or another browser on the iPhone. The URL normally looks like:

```text
https://<macbook-tailnet-name>.<tailnet>.ts.net/ui/gui_html.html
```

The exact URL comes from Tailscale. LocalGPT should show or copy it only when the trusted backend handler can confirm an available Tailscale Serve address.

## Daily Use

1. Keep the MacBook awake.
2. Start LocalGPT on the MacBook.
3. Keep Tailscale connected on both devices.
4. Open the Tailscale Serve URL on the iPhone.

If the LocalGPT backend port changed since the previous launch, rerun:

```bash
tailscale serve --bg http://127.0.0.1:<LOCALGPT_PORT>
```

with the new active port.

## What Not To Do

- Do not run `tailscale funnel` for normal LocalGPT access.
- Do not configure router port forwarding.
- Do not bind LocalGPT directly to a public interface.
- Do not publish the LocalGPT backend with a public tunnel.
- Do not treat the iPhone as the model host; it is only the UI client.

## Quick Checks

On the MacBook:

```bash
tailscale status
tailscale serve status
curl -fsS http://127.0.0.1:<LOCALGPT_PORT>/health
```

On the iPhone:

- Tailscale app is connected.
- The iPhone is logged into the same tailnet.
- The Serve URL opens with `https://`.
- If it fails, check MacBook sleep, LocalGPT runtime, and the active backend port before changing any network exposure settings.
