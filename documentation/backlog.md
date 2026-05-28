# Backlog

This document lists future ideas that are intentionally not implemented in the current Tailscale Plugin + Secure Remote Access work.

## Future: Settings Log Cleanup Button

Status: future idea, not implemented.

Add a settings action that lets the user delete runtime logs from the UI.

Initial scope:

- clear `tmp_logs/chat.log`;
- clear `tmp_logs/pipeline.log`;
- clear `tmp_logs/transcribe.log` and `tmp_logs/transcribe.log.1`;
- show a confirmation dialog before deletion;
- keep automatic log rotation as the default background safeguard.

## Future: Caddy Official/Internal Plugin

Status: future stage, not implemented.

A future Caddy official/internal plugin could expose LAN reverse-proxy state through the same registry model used by Tailscale:

- metadata under `plugins/caddy/plugin.json`;
- trusted backend-owned handler under `backend/apps/plugins/`;
- read-only status for Caddy availability and listener state;
- network address provider item for LAN HTTPS when reachable;
- user-facing docs for LAN access.

Constraints for that future work:

- do not execute code from `plugins/caddy/`;
- do not replace the existing LAN launcher until the design is explicit;
- do not change Caddy runtime behavior unless the stage specifically calls for it;
- preserve the LAN fast path.

## Future: External Plugin Process API

Status: future idea, not implemented.

An external plugin process API could allow separately sandboxed processes to provide capabilities through a narrow IPC contract. That is not part of Plugin Registry v0.

Any future design must answer:

- process isolation and permissions;
- installation and update trust model;
- transport protocol;
- lifecycle management;
- timeout and resource limits;
- logging and auditability;
- how to prevent plugins from reading private local data by default;
- how to prevent plugins from exposing LocalGPT publicly.

Until that exists, LocalGPT only supports metadata manifests plus backend-owned trusted handlers.

## Future: Plugin Marketplace

Status: future idea, not implemented.

Marketplace installation would require a trust, signing, update, review, and rollback model. It is out of scope for the current local registry.

## Future: Plugin Hot Reload

Status: future idea, not implemented.

Hot reload of arbitrary plugin code is intentionally not supported. LocalGPT must not import or execute code from `plugins/`.

## Not Planned For This Task

The current task does not migrate these existing app areas into plugins:

- ASR;
- TTS;
- RAG;
- OCR;
- chat/model runtime.

Those remain normal LocalGPT app modules.

## Current Priority After Stage 6

Next durable cleanup step:

- refresh source docs and hub copies;
- run final checks;
- keep `documentation/README.md` and `documentation/map.md` pointed at durable docs only.
