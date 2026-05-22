# LocalGPT Documentation Map

This map gives a quick orientation across the documentation-hub files.

| File | Source | What it is for |
| --- | --- | --- |
| [tailscale-plugin-plan.md](tailscale-plugin-plan.md) | temporary hub document | Working plan, stage checklist, safety rules, and context-compaction handoff notes for the Tailscale Plugin task. Delete after the task is complete. |
| [README.project.md](README.project.md) | `README.md` | Main project overview: launch flows, user-facing scenarios, LAN runtime notes, environment examples, and project structure. Read this first. |
| [TECHNICAL_README.md](TECHNICAL_README.md) | `TECHNICAL_README.md` | Technical architecture reference: backend/UI runtime, contracts, LAN diagnostics, static UI system, and implementation notes. |
| [README.backend_structure.md](README.backend_structure.md) | `backend/README.md` | Backend structure map: packages, API areas, runtime contracts, static UI serving, and backend maintenance notes. |
| [README.rag.md](README.rag.md) | `rag_sources/README.md` | RAG source folder notes: what belongs in the RAG source area and how the folder is intended to be used. |
| [ui-components.md](ui-components.md) | `docs/ui-components.md` | UI component notes and frontend conventions for the LocalGPT interface. |
| [Instructions_for_GPT.md](Instructions_for_GPT.md) | `Instructions_for_GPT.md` | Full instruction set for GPT/Codex-style assistants working on this project. |
| [Instructions_for_GPT_Context.md](Instructions_for_GPT_Context.md) | `Instructions_for_GPT_Context.md` | Context-heavy assistant instructions for preserving project decisions and development constraints. |
| [Instructions_for_GPT_Short.md](Instructions_for_GPT_Short.md) | `Instructions_for_GPT_Short.md` | Short assistant instructions for quick project handoff or constrained contexts. |
| [system_base.prompt.md](system_base.prompt.md) | `app/prompts/system_base.md` | Base runtime prompt used by the app. Useful when reviewing assistant behavior and model-facing defaults. |
| [CLEANUP_REPORT.md](CLEANUP_REPORT.md) | `CLEANUP_REPORT.md` | Cleanup and maintenance notes, including naming and compatibility decisions. |

## Suggested Reading Order

1. [README.project.md](README.project.md)
2. [TECHNICAL_README.md](TECHNICAL_README.md)
3. [README.backend_structure.md](README.backend_structure.md)
4. [ui-components.md](ui-components.md)
5. [Instructions_for_GPT_Short.md](Instructions_for_GPT_Short.md)

## Remote Access Notes

LAN runtime documentation is currently in [README.project.md](README.project.md) and [TECHNICAL_README.md](TECHNICAL_README.md).

Tailscale-specific documents are planned for the remote-access documentation stage:

- `remote-access-tailscale.md`
- `how-to-use-tailscale-mode.md`
