# Repository safety and contribution rules

## Personal data and test exports

Before every commit, inspect all staged paths and review added text hunks. Before every push or pull request, repeat the review over the complete proposed branch range against its target branch (normally `origin/dev`). Run:

```sh
python scripts/check_commit_data.py --staged
python scripts/setup_repo_safety.py gate --when commit
```

Before publishing a branch or opening/updating a PR, run:

```sh
python scripts/check_commit_data.py --range origin/dev
python scripts/setup_repo_safety.py gate --when push
gitleaks git . --log-opts='origin/dev..HEAD' --redact
```

On every clone, run `python scripts/setup_repo_safety.py install` once to create the local safety environment and configure the tracked fail-closed hooks. The hooks use repository-relative paths and restore scanner discovery for GUI clients. Install required scanners as documented in `docs/repo-safety.md`. Never use `--no-verify` to bypass checks.

## Branches

Do not create or switch to a separate branch for every task. Create or switch branches only when the user explicitly asks or an applicable instruction requires it. If a separate branch seems materially useful, explain why and ask before switching.

## Model routing

- UI layout and visual implementation: GPT-6 Luna, High.
- Complex backend work: GPT-6.1 Sol, High.
- General implementation and bounded follow-up fixes: GPT-6.1 Sol, Medium.
- Audits explicitly requested by the user: GPT-6 Astra or GPT-6.1 Sol, High. After a High audit provides findings or recommendations, bounded fixes may use GPT-6.1 Sol, Medium.

Apply these routes to execution only. A direct user choice for a task takes precedence. When delegating, select the requested model and effort explicitly if the runtime supports it; report the effective executor only when runtime metadata exposes it. Do not start an independent audit automatically unless the user asks for it.

## Parallel work and agents

- For a request with multiple independent workstreams, delegate them to separate agents and run them in parallel when the runtime supports it. Prefer clear boundaries such as backend, frontend, tests, or disjoint file groups.
- Before parallel edits, assign ownership so agents do not modify the same files. If workstreams are tightly coupled or share files, keep implementation under one coordinating agent and delegate only independent research or review.
- The coordinating agent integrates the results, resolves conflicts, checks the combined diff, and runs the relevant validation before reporting completion.
- Do not create agents for small, bounded tasks where coordination would cost more than the parallel work saves. Respect the model routes above and any explicit user choice.

Only `.gitkeep` files may be proposed under `rag_sources/` or `app/data/`. Do not commit Telegram exports, user documents, databases, attachments, generated profile data, credentials, or other runtime files. Test fixtures must be synthetic and must not be copied from a user's real export.

If any candidate file, filename, or added content appears to contain personal data, a real export, database/runtime data, credentials, or non-synthetic test material—or if its status is uncertain—stop. Do not commit, push, create a PR, or update an existing PR until the user decides how to handle it. Report only the relevant paths and ask the user; do not print suspected personal contents. Remove or replace approved data locally before rerunning the complete checks.

The path audit is a guardrail, not a content classifier. Review the proposed diff for personal information even when the path audit passes. For PR checks, use the actual target branch if it differs from `origin/dev`.
