# Support

## Start here

For installation, configuration, and normal operation, read:

- [README.md](README.md)
- [docs/USER_GUIDE.md](docs/USER_GUIDE.md)
- [docs/STATUS_SCHEMA.md](docs/STATUS_SCHEMA.md)
- [docs/TEST_REPORT.md](docs/TEST_REPORT.md) for the dated release-candidate validation record

Common local checks:

1. Confirm Windows can find Git, Node.js, npm, and the Python `py` launcher.
2. Run `install.bat` after dependency or frontend changes.
3. Confirm the production service responds at `http://127.0.0.1:8765/api/health`.
4. Check whether another process already owns port 8765.
5. Review the local server error log under `data/`. Treat it as sensitive and redact paths, repository facts, and other private data before sharing any excerpt.
6. Confirm the selected path is a Git repository or linked worktree.

## Ask for help

Use the repository's bug report form for reproducible defects and the feature request form for proposed improvements. Search existing issues first.

Include:

- the commit or release used;
- Windows, Python, Node.js, npm, and Git versions;
- the command that failed and its exit code;
- minimal reproduction steps using a synthetic repository;
- expected and observed behavior; and
- tests or workarounds already tried.

Do not attach a real database, raw log, `.env`, repository archive, browser profile, or unredacted screenshot. Replace private paths and names with examples while preserving the structure needed to reproduce the issue.

## Security and privacy issues

Do not use a public support issue for a vulnerability or privacy leak. Follow [SECURITY.md](SECURITY.md).

## Support boundaries

This project can help diagnose its own installation, API, UI, scanning, and status-metadata behavior. It cannot provide:

- recovery guarantees for an unrelated Git repository;
- help obtaining or sharing credentials;
- support for exposing the current single-user service to an untrusted network;
- private Codex conversation access or agent-operation support;
- GitHub/GitLab pull-request or CI administration; or
- guaranteed response times.

The project is maintained on a best-effort basis.
