# Changelog

This file records user-visible changes intended for public releases. Dates and version numbers will be added only after a release is approved and actually created.

## Unreleased

### Added

- English and Simplified Chinese project overviews with an explicit local-only scope.
- Security reporting, privacy, support, contribution, and community conduct policies.
- Pull request and structured bug/feature request templates.
- An initial third-party license inventory and safe environment-variable reference.
- A least-privilege Windows CI workflow, Dependabot configuration, and hash-locked Python application/test environment.
- Reproducible Playwright capture for two privacy-reviewed screenshots from the running application and synthetic Git data.

### Changed

- Public documentation now uses neutral examples instead of private project names or machine-specific paths.
- Project claims now distinguish read-only Git observation from explicit status-metadata writes and local open actions.
- First start now uses an empty project registry; repositories are added through the UI or created as isolated synthetic demos.
- Native directory and local open actions are disabled by default and require `CPC_ENABLE_SYSTEM_ACTIONS=1`; additional browser origins are explicit through `CPC_ALLOWED_ORIGINS`.
- Node.js support is documented precisely as `^20.19.0 || >=22.12.0`; Python application/test artifacts are locked for 64-bit CPython 3.11 on Windows.
- Unsupported features such as agent orchestration, cloud sync, pull-request management, CI orchestration, and automatic Git mutation are stated explicitly.

### Security

- Native terminal launching now uses a fixed executable and `cwd` instead of constructing a shell command; local actions accept only exact registered directories and reject files, UNC paths, and reparse points.
- HTTP Host and Origin boundaries, WebSocket Origin/message limits, request-size limits, security headers, no-store API responses, and opt-in native actions now protect the localhost browser boundary.
- Git inspection now uses a centralized command allow list, disables optional locks and repository fsmonitor execution, clears inherited `GIT_*` variables, caps output, and redacts credential-shaped output.
- Status metadata writes validate schema and path containment, reject reparse points, and bound backups, SQLite events, request data, and concurrent scans.
- FastAPI, Starlette, pip, setuptools, pytest, and pytest-asyncio were updated to the versions recorded in the release lock. The dependency audit for the exact release candidate is still pending and must be recorded in `docs/TEST_REPORT.md`; that audit checks known advisories and cannot prove the software vulnerability-free.
- Public release remains blocked until the owner selects a license, approves the copyright notice, completes resource provenance review, and confirms that publishable Git history contains no private configuration or unapproved binary assets.

### License

- License selection remains pending. This changelog does not grant permission to use, copy, modify, or redistribute the project.
