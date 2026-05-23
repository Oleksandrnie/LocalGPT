# LocalGPT Documentation Map

This map gives a quick orientation across the documentation-hub files.

| File | Source | What it is for |
| --- | --- | --- |
| [README.project.md](README.project.md) | `README.md` | Main project overview: launch flows, user-facing scenarios, LAN runtime notes, environment examples, and project structure. Read this first. |
| [TECHNICAL_README.md](TECHNICAL_README.md) | `TECHNICAL_README.md` | Technical architecture reference: backend/UI runtime, contracts, LAN diagnostics, static UI system, and implementation notes. |
| [README.backend_structure.md](README.backend_structure.md) | `backend/README.md` | Backend structure map: packages, API areas, runtime contracts, static UI serving, and backend maintenance notes. |
| [plugin-architecture.md](plugin-architecture.md) | durable hub document | Plugin Registry v0 architecture: metadata-only manifests, trusted backend handlers, enabled state, and network address provider contract. |
| [remote-access-tailscale.md](remote-access-tailscale.md) | durable hub document | Technical reference for private-tailnet Tailscale remote access to LocalGPT, including security rules and handler constraints. |
| [how-to-use-tailscale-mode.md](how-to-use-tailscale-mode.md) | durable hub document | User-facing Tailscale mode checklist for MacBook runtime and iPhone browser-client access. |
| [README.rag.md](README.rag.md) | `rag_sources/README.md` | RAG source folder notes: what belongs in the RAG source area and how the folder is intended to be used. |
| [ui-components.md](ui-components.md) | `docs/ui-components.md` | UI component notes and frontend conventions for the LocalGPT interface. |
| [Instructions_for_GPT.md](Instructions_for_GPT.md) | `Instructions_for_GPT.md` | Full instruction set for GPT/Codex-style assistants working on this project. |
| [Instructions_for_GPT_Context.md](Instructions_for_GPT_Context.md) | `Instructions_for_GPT_Context.md` | Context-heavy assistant instructions for preserving project decisions and development constraints. |
| [Instructions_for_GPT_Short.md](Instructions_for_GPT_Short.md) | `Instructions_for_GPT_Short.md` | Short assistant instructions for quick project handoff or constrained contexts. |
| [system_base.prompt.md](system_base.prompt.md) | `app/prompts/system_base.md` | Base runtime prompt used by the app. Useful when reviewing assistant behavior and model-facing defaults. |
| [CLEANUP_REPORT.md](CLEANUP_REPORT.md) | `CLEANUP_REPORT.md` | Cleanup and maintenance notes, including naming and compatibility decisions. |
| [backlog.md](backlog.md) | durable hub document | Future plugin backlog. Caddy official/internal plugin and External Plugin Process API are listed as future work only. |

## Suggested Reading Order

1. [README.project.md](README.project.md)
2. [TECHNICAL_README.md](TECHNICAL_README.md)
3. [README.backend_structure.md](README.backend_structure.md)
4. [plugin-architecture.md](plugin-architecture.md)
5. [remote-access-tailscale.md](remote-access-tailscale.md)
6. [how-to-use-tailscale-mode.md](how-to-use-tailscale-mode.md)
7. [ui-components.md](ui-components.md)
8. [Instructions_for_GPT_Short.md](Instructions_for_GPT_Short.md)

## Remote Access Notes

LAN runtime documentation is currently in [README.project.md](README.project.md) and [TECHNICAL_README.md](TECHNICAL_README.md).

Tailscale-specific documents:

- [remote-access-tailscale.md](remote-access-tailscale.md)
- [how-to-use-tailscale-mode.md](how-to-use-tailscale-mode.md)

Plugin architecture and future backlog:

- [plugin-architecture.md](plugin-architecture.md)
- [backlog.md](backlog.md)
