from __future__ import annotations

from pathlib import Path
from typing import Any

from .git_runner import GitCommandError, run_git
from .path_safety import is_unc_or_device_path


MAX_WORKTREES = 100


class WorktreeScanner:
    def scan(self, repo_path: str | Path) -> list[dict[str, Any]]:
        output = run_git(repo_path, ["worktree", "list", "--porcelain"])
        records: list[dict[str, Any]] = []
        current: dict[str, Any] = {}
        for raw_line in [*output.splitlines(), ""]:
            line = raw_line.strip()
            if not line:
                if current:
                    if len(records) >= MAX_WORKTREES:
                        raise GitCommandError("Repository exceeds the supported worktree limit")
                    path = Path(current["path"])
                    current["path_exists"] = path.exists()
                    current.setdefault("branch", None)
                    current.setdefault("head_sha", None)
                    current.setdefault("is_bare", False)
                    current.setdefault("is_locked", False)
                    current.setdefault("is_prunable", False)
                    records.append(current)
                    current = {}
                continue
            key, _, value = line.partition(" ")
            if key == "worktree":
                if is_unc_or_device_path(value):
                    raise GitCommandError("Worktree metadata contains a remote or device path")
                current["path"] = str(Path(value).resolve())
            elif key == "HEAD":
                current["head_sha"] = value
            elif key == "branch":
                current["branch"] = value.removeprefix("refs/heads/")
            elif key == "bare":
                current["is_bare"] = True
            elif key == "locked":
                current["is_locked"] = True
                current["locked_reason"] = value or None
            elif key == "prunable":
                current["is_prunable"] = True
                current["prunable_reason"] = value or None
            elif key == "detached":
                current["branch"] = "DETACHED"
        return records
