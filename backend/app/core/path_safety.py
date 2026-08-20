from __future__ import annotations

import os
from pathlib import PureWindowsPath


def is_unc_or_device_path(value: str | os.PathLike[str]) -> bool:
    """Identify Windows UNC and device namespaces without touching the filesystem."""
    candidate = os.fspath(value).strip()
    normalized = candidate.replace("/", "\\")
    return normalized.startswith("\\\\") or PureWindowsPath(candidate).drive.startswith("\\\\")
