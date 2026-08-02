# Fix Caddy LAN Progress

## Task

- Goal: restore reliable private-LAN HTTPS access through the LocalGPT Caddy launcher.
- Problem: the phone-access UI reports the Caddy URL as unavailable.
- Expected result: the LAN launcher starts Caddy against the active localhost backend and backend metadata exposes a usable LAN URL.
- Source specification: user request and supplied UI screenshot, 2026-08-03.
- Branch: `codex/fix-caddy-lan`.
- Started: 2026-08-03.
- Current status: in progress.
- Current stage: Stage 3 — validate and clean up.

## Instructions and precedence

- Direct user requirements: investigate and fix Caddy/LAN; create a branch; use staged progress workflow.
- Applicable AGENTS.md rules: read networking/testing docs; preserve localhost backend and no public exposure; maintain progress file and focused commits.
- Git authorization: branch creation explicitly authorized; repository workflow requires focused stage commits for tracked changes.

## Scope lock

### In scope

- macOS LAN launcher, generated Caddy configuration/lifecycle, and LAN metadata contract.
- Targeted regression coverage and affected networking documentation.

### Out of scope

- Tailscale, public exposure, unrelated UI redesigns, and model/runtime changes.

### Risks and rollback concerns

- LAN availability depends on real private-network state and Caddy local-CA trust; backend must remain loopback-only.

## Baseline

- Current branch before work: `dev`, clean working tree; switched to `codex/fix-caddy-lan`.
- Observed behavior: phone-access UI shows Caddy URL as unavailable.
- Existing relevant implementation: `tools/LTrnsrb.sh`, `app/routes/meta.py`, `start_localgpt_lan.*`.
- Existing relevant docs read: `docs/README.md`, `docs/ARCHITECTURE.md`, `docs/knowledge/networking.md`, `docs/TESTING.md`.

## Implementation stages

### Stage 1 — Diagnose runtime and launcher contract

- Goal: identify the confirmed cause from current runtime state, launcher code, and metadata behavior.
- Status: completed
- Validation: shell syntax checks, Caddy config validation where available, and targeted metadata inspection.
- Completion criterion: completed. Normal launcher had no Caddy process; the LAN script's LaunchAgent set `WorkingDirectory` to the project path and Caddy then hung before opening its listener. The generated config works through launchd with a temporary runtime working directory.
- Proposed checkpoint commit: none (research-only).

### Stage 2 — Repair LAN startup and metadata

- Goal: implement the smallest safe fix and add regression coverage where feasible.
- Status: completed
- Validation: targeted tests, shell syntax/config validation, and localhost HTTPS proxy smoke.
- Completion criterion: completed. `start_localgpt.command` started Caddy through launchd with its runtime directory as `WorkingDirectory`; `https://172.20.10.2:8443/health` returned `ok` and backend `/health` reported the LAN UI URL.
- Proposed checkpoint commit: `fix(network): restore Caddy LAN launcher`.

### Stage 3 — Validate and clean up

- Goal: run proportional checks, update affected permanent records, and close task state.
- Status: pending
- Validation: baseline static checks plus LAN-focused smoke and diff review.
- Completion criterion: requirements verified or exact external LAN limitation recorded.
- Proposed checkpoint commit: `docs(network): record Caddy LAN launcher fix`.

## Decisions

- Keep the backend on `127.0.0.1`; Caddy remains the only LAN-facing listener.
- Make the ordinary macOS no-argument launch path start the private LAN proxy automatically. Explicit launcher arguments retain direct local behavior.
- Set Caddy's LaunchAgent working directory to its runtime directory, not the project directory. Caddy has no need for the project directory and this avoids the reproduced launchd startup hang.

## Continuation state

- Next exact action: inspect the stage diff, create the Stage 2 checkpoint, then run proportional baseline validation and update the changelog before final cleanup.

## Validation results

- Stage 2 shell/config checks: `/bin/zsh -n tools/LTrnsrb.sh`, `/bin/zsh -n start_localgpt.command`, `/bin/sh -n start_localgpt.sh`, and `git diff --check` passed.
- Stage 2 live LAN smoke: passed on `172.20.10.2:8443`; Caddy listener, HTTPS `/health`, backend LAN metadata, and LaunchAgent runtime working directory were verified.
- Certificate note: Caddy reports that it cannot use `sudo` to install the local CA from the non-interactive LaunchAgent. The proxy still serves HTTPS; client trust remains a separate first-device requirement.

## Changed files

### Added

- `docs/progress/fix-caddy-lan-progress.md`

### Modified

- `tools/LTrnsrb.sh`
- `start_localgpt.command`
- `start_localgpt.sh`
- `README.md`
- `docs/knowledge/networking.md`
