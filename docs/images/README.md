# Screenshot provenance

The images in this directory are captures of the real Codex Project Hub web application. They use a temporary Git repository and SQLite database created by the Playwright documentation test; no production repository, user profile, remote service, or private application data is used.

| File | View | Demo data |
|---|---|---|
| `dashboard-overview.webp` | Multi-project overview | `Project Alpha` |
| `project-dashboard.webp` | Project topology and task detail | `Project Alpha`, `Example Dashboard Task`, and example branches |

The test first captures the page as PNG through Playwright, then Chromium converts those same pixels to WebP. No generative image tool, mockup, or third-party visual asset is involved.

After installing the documented dependencies, regenerate both images from the repository root with:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/capture-docs-screenshots.ps1
```

Before committing regenerated images, inspect them at full resolution for local paths, personal data, credentials, browser chrome, and unexpected test artifacts.
