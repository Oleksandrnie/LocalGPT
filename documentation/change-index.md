# Change Index

## 2026-08-02 — LocalGPT first-time setup
- Scope: dependency audit, cross-platform setup launchers, runtime environment preparation, and setup documentation.
- Result: Added interactive macOS/Linux/Windows setup with OS/package-manager detection, explicit installation confirmations, idempotent dependency checks, and no automatic model/data/config/network changes.
- Key files: `setup/setup_localgpt.py`, `setup_localgpt.command`, `docs/DEPENDENCIES.md`
- Verification: static baseline and focused setup tests passed; clean-machine installer acceptance deferred by user approval.
