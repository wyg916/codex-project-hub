# Privacy and Local Data

Codex Project Hub is a local-first, single-user development dashboard. It does not currently include cloud synchronization, hosted accounts, analytics, or application telemetry.

This document describes the data visible to the application and where that data is stored. It is not a substitute for reviewing a specific deployment.

## Data the application reads

For each repository that a user explicitly registers, the application may read:

- repository and worktree filesystem paths;
- local branch names and checked-out branches;
- commit identifiers, messages, authors, and timestamps;
- configured remote URLs, with credentials redacted before display;
- upstream, ahead/behind, merge-base, and merged-state facts;
- modified, added, deleted, untracked, and conflicted file paths;
- Git common-directory metadata; and
- explicit project and task status metadata under `codex-dashboard/`.

These values can reveal private project names, usernames, internal directory structures, work in progress, and contributor identities. Treat the dashboard, API responses, logs, database, and screenshots as sensitive local material.

## Data the application writes

| Location | Contents | Trigger |
|---|---|---|
| `<CPC_DATA_DIR>/control-center.db` | Project registrations, snapshots, and application activity | Normal application use; defaults to `data/` |
| `<CPC_DATA_DIR>/*.log` | Local server output and errors | Windows launch scripts |
| `<CPC_DATA_DIR>/*.pid` | IDs for processes started by this project | Start and development scripts |
| `<CPC_DATA_DIR>/server.start.lock` | Short-lived start-operation coordination lock | Windows start script |
| `<git-common-dir>/codex-dashboard/status.json` | Explicit project and branch task metadata | Explicit API or helper-script update |
| `<git-common-dir>/codex-dashboard/*.bak.json` | Backup of replaced valid status metadata | Explicit status update |
| `<git-common-dir>/codex-dashboard/status.lock` | Cross-process coordination for explicit metadata updates | Explicit API or helper-script update |

The Git scanner does not automatically modify monitored business code or run merge, rebase, reset, clean, branch deletion, fetch, or push operations.

## Network behavior

- The production launcher serves the browser application and API on `127.0.0.1:8765`.
- Development mode also runs Vite on `127.0.0.1:5173`.
- Browser updates use the local API and a local WebSocket connection.
- Browser origins are limited to built-in loopback origins plus explicit HTTP(S) additions in `CPC_ALLOWED_ORIGINS`.
- API responses use `Cache-Control: no-store` so repository paths, commit metadata, and other local facts are not intentionally retained in the browser HTTP cache; static frontend assets remain cacheable.
- The application does not configure built-in analytics, telemetry, cloud synchronization, or automatic Git remote access.
- Installation contacts PyPI/Python package hosts, the npm registry configured on the machine, and Playwright's configured Chromium download host.
- Opening a link or using an external editor is governed by that external application, not by this privacy statement.

Do not expose the service directly to another network. The application currently has no multi-user authentication boundary.

## Local system actions

The native directory picker and local Explorer, terminal, and Visual Studio Code actions are disabled by default. Set `CPC_ENABLE_SYSTEM_ACTIONS=1` only when those actions are explicitly wanted on a trusted local machine. Local open requests must exactly match a registered repository root or one of its worktrees.

## Retention and deletion

Deleting a project registration in the UI does not delete the underlying Git repository. To remove the dashboard's remaining local state:

1. Stop the application.
2. Review and remove the appropriate files under `CPC_DATA_DIR` (the project `data/` directory by default).
3. Separately review `<git-common-dir>/codex-dashboard/` in repositories whose explicit task metadata should be removed.
4. Review screenshots, exported logs, shell history, and backups separately; they are not erased by deleting a registration.

Back up anything that must be retained before deleting local state.

## Configuration and screenshots

- Do not commit a configuration containing real local repository paths or private project names.
- Use obvious examples such as `Example Project Alpha` and `C:\Projects\ExampleProject` in public documentation.
- Before sharing a screenshot, remove usernames, absolute paths, private repository names, email addresses, remote URLs, notifications, avatars, tokens, and real task text.
- Public project screenshots must come from the running application with synthetic demo repositories. A concept image or generated UI mockup must not be represented as a product screenshot.

## Security reports

Privacy leaks and unintended data access should be reported privately using [SECURITY.md](SECURITY.md). Do not attach unredacted private data to a public issue.
