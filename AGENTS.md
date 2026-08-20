# Codex Project Hub engineering rules

- Treat every registered repository as read-only except for documented `codex-dashboard` status metadata explicitly written by the status API or helper script.
- Run only the Git subcommands allow-listed by the central Git runner. Do not add merge, rebase, reset, clean, checkout, branch deletion, or arbitrary command execution.
- Derive Git facts only from Git command output. Derive task progress only from explicit status metadata; show `未维护` when metadata is missing and `UNKNOWN` when a Git fact is unavailable.
- Keep the backend bound to loopback by default. Preserve Host and Origin checks, path containment, secret redaction, and safe-disabled native system actions.
- Never commit local databases, logs, process IDs, environment files, private audit material, generated test output, or screenshots containing real repository data or machine-specific paths.
- After a focused change, run the relevant tests. Before release, run pytest, Vitest, the frontend production build, Playwright at the three documented resolutions, and two one-click startup checks.
- Do not describe unimplemented agent orchestration, cloud sync, pull-request management, CI orchestration, or automatic Git mutation as current functionality.
