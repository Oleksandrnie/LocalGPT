# Tailscale Removal Progress

## Goal
Remove the unused Tailscale integration from the current audit branch while preserving the explicitly authorized LAN/local runtime behavior, and keep current docs/tests accurate.

## Acceptance criteria
- No active runtime, installer, UI, test, README, dependency, or current networking-doc integration for Tailscale remains.
- Generic plugin registry behavior unrelated to Tailscale remains intact.
- Existing local-only default and optional LAN behavior stay unchanged.
- Current readiness report describes the resulting network posture and no longer lists Tailscale as a dependency or blocker.
- Targeted tests and proportional static checks pass; final diff is committed and worktree clean.
- Do not publish/create the future public repository, rewrite Git history, modify the project license, or rotate credentials in this task.

## Scope
- Tailscale backend handler/plugin manifest/docs, registry wiring, installer prompt and runtime mode/status paths.
- Current README, dependency/networking/plugin/architecture/readiness documentation, changelog/backlog where factual.
- Tests that assert the Tailscale integration.

## Risks and constraints
- Keep LAN Caddy behavior distinct; removing Tailscale does not by itself remove LAN API exposure.
- Preserve user data and the existing multimodal progress record.
- Do not modify/rewrite any Git history. The user authorized a clean Tailscale-removal commit on the existing task branch.
- Piper licensing discussion and a clean new public repository are future owner-directed work, not implementation scope here.

## Stages
1. Inspect current plugin, installer, launch modes, docs, tests and references. **Completed**
2. Remove Tailscale-specific implementation and update current docs/tests. **Completed**
3. Review diff, create the implementation checkpoint, then delete this progress record in a cleanup commit. **In progress**

## Status
- Branch: `codex/opensource-readiness-audit`.
- Start state: clean at `f321d0b`.
- Current stage: final review and checkpoint.
- Decisions: remove Tailscale completely from current runtime/setup; keep LAN+Caddy path and its unauthenticated API risk visible; do not change root license, create the future public repository, rotate credentials or rewrite Git history.
- Code changes: removed trusted Tailscale handler registration, UI status renderer, installer option, `LOCALGPT_REMOTE_ACCESS_MODE` output/example entry, and default CORS allowance for the Tailscale CGNAT range. Generic plugin metadata registry and LAN network-address path remain.
- Documentation changes: updated README, AGENTS, networking/plugins/backend/architecture/dependencies/testing docs, backlog and current readiness report; added changelog entry. Historical audit/changelog references remain historical.
- Removed files: `backend/apps/plugins/tailscale.py` and `plugins/tailscale/`.
- Added regression test for default CORS local/private LAN origins and rejection of Tailscale CGNAT/public origins.
- Validation passed: `RAG_EMBEDDING_PROVIDER=local_hash venv/bin/python -m unittest tests.test_plugin_registry tests.test_prompt_rag_security_audit tests.test_setup_dependencies tests.test_lan_launcher tests.test_networking_config -v` (64 tests); `node --test tests/*.test.mjs` (51); `node tests/markdown_rendering.test.mjs` (4); `venv/bin/python -m compileall -q app backend tests`; `node --check web_ui/js/app.js`; `git diff --check`.
- One initial targeted Python invocation omitted `RAG_EMBEDDING_PROVIDER=local_hash`; prompt/RAG test setup attempted a live Ollama request and failed because no local service was listening. Re-running with the deterministic provider passed all 64 tests. No live model/network test was performed.
- Residual Tailscale text is limited to this current audit/changelog removal note, the CGNAT regression fixture, and the older historical prompt/RAG audit/changelog entry; runtime, installer and current usage documentation no longer reference the integration.
- Next action: stage only task-owned source/docs/tests and this progress file, inspect the staged diff, create `chore(networking): remove Tailscale integration`, then delete this progress file in a cleanup commit.
