# Contributing

Thank you for helping improve Codex Project Hub.

## Pre-release licensing gate

The project has not selected an open-source license. Until a `LICENSE` file and contribution terms are approved, substantive code contributions cannot be merged. You may still report bugs, propose changes, and improve release-preparation documentation, but do not assume that the absence of a license grants permission to reuse or redistribute the code.

## Before opening an issue

- Read [README.md](README.md), [SUPPORT.md](SUPPORT.md), and the existing issue forms.
- Search for an existing report.
- Reproduce the problem with an isolated or synthetic repository where possible.
- Remove real repository names, usernames, absolute paths, remote URLs, commit authors, tokens, and customer data.
- Report vulnerabilities privately according to [SECURITY.md](SECURITY.md).

## Development setup

Requirements are Windows 10/11, 64-bit CPython 3.11.x, Node.js `20.19.x` or `22.12.0` and later (`^20.19.0 || >=22.12.0`), npm, and Git. Node.js 21 is not supported by the current Vite toolchain.

```bat
install.bat
dev.bat
```

The backend is served on `127.0.0.1:8765`; Vite development assets are served on `127.0.0.1:5173`.

### Updating Python dependencies

`backend/pylock.toml` is intentionally platform-specific. Regenerate it only on Windows x86-64 with CPython 3.11 and the bootstrapped pip 26.2.1 whenever a direct pin in `backend/requirements*.txt` changes:

```powershell
.venv\Scripts\python.exe -m pip install --require-hashes -r backend\requirements-bootstrap.txt
.venv\Scripts\python.exe -m pip lock --only-binary=:all: -r backend\requirements-dev.txt -o backend\pylock.toml
.venv\Scripts\python.exe scripts\verify-python-lock.py
.venv\Scripts\python.exe -m pip install -r backend\pylock.toml
.venv\Scripts\python.exe -m pip check
.venv\Scripts\python.exe -m pip_audit --local --strict --progress-spinner off
```

Review the resulting artifact URLs, hashes, transitive licenses, and `THIRD_PARTY_NOTICES.md` inventory in the same change. A direct-pin update without the matching lock and notice update is incomplete.

## Design constraints

Changes must preserve these boundaries:

- Git facts come from actual command results.
- Scanning monitored repositories uses only the documented read-only Git allow list.
- Git subprocess calls pass arguments as arrays rather than interpolated shell strings.
- Task progress comes only from explicit status metadata; missing values remain “not maintained” or `UNKNOWN`.
- The application does not automatically alter monitored business code or Git history.
- Filesystem and system actions remain inside registered repository or worktree boundaries.
- Loopback binding remains the safe default.
- Logs, fixtures, screenshots, and documentation contain only synthetic data.

Changes to Git commands, path validation, status writes, process launching, logs, WebSockets, or remote URL handling require focused security tests.

## Tests

Run the full local gate before requesting review:

```bat
test-all.bat
```

This includes pytest, Vitest, the TypeScript/Vite production build, Playwright, and helper-script checks. For a focused change, run the affected suite while iterating, then run the full gate before handoff.

Do not update a dated test report unless the documented command was actually run. Record failures as failures rather than changing expected results to hide them.

## Pull requests

Keep changes small and explain:

- the user-visible problem and intended result;
- the affected security or privacy boundaries;
- commands and tests actually run;
- screenshots, when UI behavior changes; and
- remaining limitations or follow-up work.

Use a feature or fix branch rather than committing directly to the default branch. Stage only the files that belong to the change. Do not include local databases, logs, PID files, `.env`, private configuration, build output, browser reports, or internal delivery archives.

## Documentation and screenshots

- Keep English `README.md` and Chinese `README.zh-CN.md` aligned for user-facing changes.
- Describe only implemented behavior.
- Use neutral demo names and generic paths.
- Screenshots must come from the running application with synthetic data and must be checked at full resolution.
- Record the creator and source of any distributable image, icon, font, template, or copied code.

## Conduct

Participation is governed by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
