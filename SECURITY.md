# Security Policy

## Release status and supported versions

Codex Project Hub publishes security fixes for the current `0.1.x` release line on a best-effort basis.

| Version | Supported |
|---|---|
| `0.1.x` | Yes |
| Older releases | No |

## Report a vulnerability privately

Do not publish exploit details, credentials, private repository names, local paths, screenshots, or proof-of-concept data in a public issue.

Use GitHub's **Report a vulnerability** flow in the repository Security tab. Private Vulnerability Reporting is enabled for this public repository. Do not use a public issue for vulnerability details.

Include, after redaction:

- the affected commit or prospective release;
- the affected component and entry point;
- prerequisites and minimal reproduction steps;
- observed and expected behavior;
- impact and the boundary crossed;
- a suggested mitigation, if known; and
- whether the issue is already public or actively exploited.

The maintainer will validate the report, coordinate a fix and disclosure plan, and credit the reporter if requested and appropriate. Response timing is best effort.

## High-priority security boundaries

Reports are especially useful when they demonstrate:

- command or argument injection through a repository path, branch name, remote URL, or status field;
- access outside a registered repository or linked worktree;
- unsafe local process launching;
- an unintended mutating or network-changing Git operation;
- leakage of credentials through a remote URL, log, API response, screenshot, or exception;
- path traversal or arbitrary file read/write;
- WebSocket or API exposure beyond the expected loopback boundary;
- stored or reflected script execution in the browser;
- corruption or unsafe overwrite of explicit status metadata; or
- an unsafe dependency or release artifact.

## Security model

- The production launcher binds the service to `127.0.0.1`.
- Git inspection is restricted to a documented read-only command allow list and uses subprocess argument arrays.
- Native directory selection and local open actions are disabled by default. They are enabled only when `CPC_ENABLE_SYSTEM_ACTIONS=1`, and local open requests must exactly match the selected registered repository root or one of its worktrees.
- Remote URLs are redacted before they are returned for display or logging.
- Explicit task status writes are separate from Git scanning and require an explicit API or helper-script action.
- Browser origins are limited to the built-in loopback origins plus explicit HTTP(S) additions in `CPC_ALLOWED_ORIGINS`; the configuration rejects credentials, non-root paths, queries, and fragments.
- `CPC_DISABLE_BACKGROUND=1` disables watchdog and background polling.

The project is not designed to be exposed directly to an untrusted network and currently has no multi-user authentication or authorization model.

## Safe disclosure and test data

Use synthetic repositories and invalid example credentials. Never attach a real SQLite database, application log, browser profile, private repository archive, or screenshot containing local paths. The helper `scripts/create-demo-repo.py` can create an isolated fixture for reproduction.

Security testing must not target systems or repositories without authorization.

## Dependency and release handling

Before each public release, maintainers should re-run dependency and secret scans, rebuild from the lock files, inspect generated screenshots and packages, and confirm that the selected license and third-party notices are complete. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
