# Add LAN Certificate Download Progress

## Task

- Goal: let a LocalGPT owner download the public Caddy root certificate from Settings → System for iPhone or Android installation.
- Expected result: the LAN settings section has separate iPhone/Android download actions, and the backend serves only Caddy's public root certificate while LAN HTTPS is active.
- Source specification: user request, 2026-08-03.
- Branch: `codex/add-lan-certificate-download`.
- Current status: in progress.
- Current stage: Stage 2 — validate and close.

## Instructions and precedence

- Direct user requirements: add certificate issuance controls next to the Caddy URL in System settings, for iPhone and Android.
- Applicable AGENTS.md rules: preserve private-network security, keep routes thin, test backend/UI changes, update progress and focused commits.
- Git authorization: branch creation is covered by the user's standing request; repository workflow requires focused stage commits.

## Scope lock

### In scope

- A read-only, no-store download endpoint for Caddy's public local root CA.
- iPhone and Android download controls with concise manual-install guidance.
- API and static UI regression coverage, networking documentation.

### Out of scope

- Private-key export, automatic certificate trust, MDM/profile generation, Caddy configuration changes, or public access.

### Risks and controls

- Expose only the regular `root.crt`, never a private key or arbitrary filesystem path.
- Require active LAN HTTPS before serving the certificate and return a clear 404 otherwise.

## Baseline

- Parent LAN repair is committed; working tree was clean before this task.
- Current LAN UI displays Caddy URL and one copy button; no certificate download endpoint or controls exist.
- Relevant implementation: `app/routes/meta.py`, `web_ui/gui_html.html`, `web_ui/js/app.js`.

## Implementation stages

### Stage 1 — Implement secure certificate download

- Status: completed
- Actions: add guarded endpoint, Settings actions, tests, and concise instructions.
- Validation: API contract tests, static UI contract test, syntax/compile checks.
- Completion criterion: completed. The endpoint is guarded by active LAN HTTPS, serves an attachment with `no-store`, and the iPhone/Android controls disable when the LAN URL is unavailable.
- Proposed checkpoint: `feat(network): add LAN certificate downloads`.

### Stage 2 — Validate and close

- Status: pending
- Actions: live LAN download smoke, full proportional validation, permanent records, cleanup.
- Completion criterion: browser/API behavior and documentation are verified; progress file removed.
- Proposed checkpoint: `docs(network): document LAN certificate downloads`.

## Decisions

- iPhone and Android buttons download the same standards-compliant public CA file; platform-specific differences are limited to safe manual installation guidance.
- The backend derives the Caddy data directory from a controlled environment override or its platform default, rather than accepting a request path.

## Continuation state

- Next exact action: inspect the stage diff, create the implementation checkpoint, then update permanent networking/testing records and run final validation.

## Validation results

- API contract tests: three tests passed for live-LAN download, unavailable-LAN rejection, and symlink rejection.
- Static UI contract: both device controls, guarded endpoint and disabled states passed.
- Static checks: `git diff --check`, JavaScript syntax and Python compilation passed.
- Live smoke: `https://172.20.10.2:8443/network/caddy/root-ca` returned a `no-store` attachment with the expected filename and byte-identical public Caddy root certificate. OpenSSL confirmed it as the Caddy Local Authority root; no private key was exposed.

## Changed files

### Added

- `docs/progress/add-lan-certificate-download-progress.md`
- `tests/test_network_certificate.py`
- `tests/lan_certificate_ui.test.mjs`

### Modified

- `app/routes/meta.py`
- `web_ui/gui_html.html`
- `web_ui/js/app.js`
