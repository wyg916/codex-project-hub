from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .git_runner import GitCommandError, redact, run_git
from .path_safety import is_unc_or_device_path
from .worktree_scanner import WorktreeScanner


MAX_CHANGED_FILES = 1000
MAX_BRANCHES = 1000


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def classify_branch(name: str, main: str, integration: str | None, rc: str | None) -> str:
    lowered = name.lower()
    if name == main:
        return "main"
    if integration and name == integration:
        return "integration"
    if rc and name == rc:
        return "rc"
    if lowered.startswith(("rc/", "rc-")):
        return "rc"
    if lowered.startswith(("release/", "release-")):
        return "release"
    if lowered.startswith(("feat/", "feature/", "codex/")):
        return "feature"
    if lowered.startswith(("fix/", "bugfix/", "hotfix/")):
        return "fix"
    if lowered.startswith(("exp/", "experiment/", "spike/")):
        return "experiment"
    if lowered.startswith(("archive/", "archived/")):
        return "archive"
    return "unknown"


class GitScanner:
    def __init__(self, timeout: float = 8.0, max_workers: int = 6):
        self.timeout = timeout
        self.max_workers = max(1, max_workers)
        self.worktrees = WorktreeScanner()

    def git(self, cwd: str | Path, args: list[str], check: bool = True) -> str:
        return run_git(cwd, args, timeout=self.timeout, check=check)

    def validate_repository(self, selected_path: str | Path) -> dict[str, Any]:
        identity = self.repository_identity(selected_path)
        root = Path(identity["repo_path"])
        try:
            branches = self._branch_names(root)
            main_branch = self._detect_main_branch(root, branches)
            remote = self.git(root, ["remote", "get-url", "origin"], check=False).strip() or None
            worktrees = self.worktrees.scan(root)
        except (GitCommandError, OSError) as exc:
            raise ValueError("仓库规模超过安全限制或无法读取") from exc
        canonical = next((item["path"] for item in worktrees if item.get("branch") == main_branch), str(root))
        return {
            "repo_path": canonical,
            "canonical_worktree": canonical,
            "git_common_dir": identity["git_common_dir"],
            "remote_url": redact(remote) if remote else None,
            "main_branch": main_branch,
            "branches": branches,
            "worktrees": worktrees,
        }

    def repository_identity(self, selected_path: str | Path) -> dict[str, str]:
        """Resolve only repository identity for startup/recovery checks."""
        if is_unc_or_device_path(selected_path):
            raise ValueError("不允许登记 UNC 或设备路径")
        path = Path(selected_path).expanduser().resolve()
        if not path.exists() or not path.is_dir():
            raise ValueError("项目目录不存在或不是文件夹")
        try:
            root_raw = self.git(path, ["rev-parse", "--show-toplevel"])
            if is_unc_or_device_path(root_raw):
                raise ValueError("仓库根目录不能是 UNC 或设备路径")
            root = Path(root_raw).resolve()
            common_raw = self.git(path, ["rev-parse", "--git-common-dir"])
        except (GitCommandError, OSError) as exc:
            raise ValueError("所选目录不属于有效 Git 仓库") from exc
        common_path = Path(common_raw)
        if is_unc_or_device_path(common_raw):
            raise ValueError("Git Common Dir 不能是 UNC 或设备路径")
        if not common_path.is_absolute():
            common_path = (path / common_path).resolve()
        return {"repo_path": str(root), "git_common_dir": str(common_path)}

    def scan_project(self, project: dict[str, Any]) -> dict[str, Any]:
        root = Path(project["repo_path"])
        identity = self.repository_identity(root)
        root = Path(identity["repo_path"])
        records = self._branch_records(root)
        branch_names = [record["name"] for record in records]
        main_branch = project.get("main_branch") or self._detect_main_branch(root, branch_names)
        integration = project.get("integration_branch") or None
        rc_branch = project.get("rc_branch") or None
        worktrees = self.worktrees.scan(root)
        checked_out = {item.get("branch"): item for item in worktrees if item.get("branch")}
        status_paths = [item["path"] for item in worktrees if item.get("path_exists") and not item.get("is_bare")]
        statuses = self._parallel_map(status_paths, self._worktree_status)
        for worktree in worktrees:
            worktree.update(
                statuses.get(
                    worktree["path"],
                    {
                        "modified_count": 0,
                        "added_count": 0,
                        "deleted_count": 0,
                        "untracked_count": 0,
                        "conflict_count": 0,
                        "changed_files": [],
                    },
                )
            )
        merged = self._merged_branches(root, main_branch)
        records_by_name = {record["name"]: record for record in records}

        def enrich(record: dict[str, str]) -> dict[str, Any]:
            name = record["name"]
            upstream = record["upstream"] or None
            ahead, behind = self._ahead_behind(root, name, upstream)
            merge_base = record["head_sha"] if name == main_branch else self.git(
                root, ["merge-base", main_branch, name], check=False
            ).strip() or None
            worktree = checked_out.get(name)
            status = statuses.get(worktree["path"], {}) if worktree else {}
            branch_type = classify_branch(name, main_branch, integration, rc_branch)
            last_time = record["head_time"] or None
            age_days = self._age_days(last_time)
            run_status = "merged" if name != main_branch and name in merged else (
                "stale" if name != main_branch and age_days is not None and age_days > 7 else "active" if worktree else "idle"
            )
            return {
                **record,
                "branch_type": branch_type,
                "status": run_status,
                "ahead": ahead,
                "behind": behind,
                "worktree_path": worktree.get("path") if worktree else None,
                "is_checked_out": bool(worktree),
                "is_merged_to_main": name != main_branch and name in merged,
                "merge_base_sha": merge_base,
                "modified_count": status.get("modified_count", 0),
                "added_count": status.get("added_count", 0),
                "deleted_count": status.get("deleted_count", 0),
                "untracked_count": status.get("untracked_count", 0),
                "conflict_count": status.get("conflict_count", 0),
                "changed_files": status.get("changed_files", []),
                "last_scan_at": utc_now(),
            }

        enriched = self._parallel_map([record["name"] for record in records], lambda name: enrich(records_by_name[name]))
        branches = [enriched[record["name"]] for record in records]
        current = self._current_branch(project.get("canonical_worktree") or root)
        remote = self.git(root, ["remote", "get-url", "origin"], check=False).strip() or None
        return {
            "project_id": project.get("id"),
            "repo_path": str(root.resolve()),
            "canonical_worktree": project.get("canonical_worktree") or str(root),
            "git_common_dir": identity["git_common_dir"],
            "remote_url": redact(remote) if remote else None,
            "main_branch": main_branch,
            "integration_branch": integration,
            "rc_branch": rc_branch,
            "current_branch": current,
            "worktrees": worktrees,
            "branches": branches,
            "last_scan_at": utc_now(),
            "scan_status": "ok",
        }

    def _branch_names(self, root: Path) -> list[str]:
        output = self.git(root, ["for-each-ref", "--format=%(refname:short)", "refs/heads"])
        branches = [line.strip() for line in output.splitlines() if line.strip()]
        if len(branches) > MAX_BRANCHES:
            raise GitCommandError("Repository exceeds the supported branch limit")
        return branches

    def _branch_records(self, root: Path) -> list[dict[str, str]]:
        fmt = "%(refname:short)%00%(objectname)%00%(upstream:short)%00%(subject)%00%(authorname)%00%(authordate:iso-strict)"
        output = self.git(root, ["for-each-ref", f"--format={fmt}", "refs/heads"])
        records = []
        for line in output.splitlines():
            fields = line.split("\x00")
            if len(fields) < 6:
                continue
            name, sha, upstream, subject, author, head_time = fields[:6]
            records.append(
                {
                    "name": name,
                    "head_sha": sha,
                    "upstream": upstream,
                    "head_message": subject,
                    "head_author": author,
                    "head_time": head_time,
                }
            )
            if len(records) > MAX_BRANCHES:
                raise GitCommandError("Repository exceeds the supported branch limit")
        return records

    def _detect_main_branch(self, root: Path, branches: list[str]) -> str:
        symbolic = self.git(root, ["symbolic-ref", "refs/remotes/origin/HEAD"], check=False).strip()
        if symbolic:
            candidate = symbolic.removeprefix("refs/remotes/origin/")
            if candidate in branches:
                return candidate
        for candidate in ("main", "master", "trunk"):
            if candidate in branches:
                return candidate
        current = self.git(root, ["symbolic-ref", "--short", "HEAD"], check=False).strip()
        return current if current in branches else (branches[0] if branches else "UNKNOWN")

    def _merged_branches(self, root: Path, main: str) -> set[str]:
        if main == "UNKNOWN":
            return set()
        output = self.git(root, ["branch", "--format=%(refname:short)", "--merged", main])
        return {line.strip() for line in output.splitlines() if line.strip()}

    def _current_branch(self, worktree: str | Path) -> str:
        current = self.git(worktree, ["symbolic-ref", "--short", "HEAD"], check=False).strip()
        if current:
            return current
        self.git(worktree, ["rev-parse", "--verify", "HEAD"])
        return "DETACHED"

    def _ahead_behind(self, root: Path, branch: str, upstream: str | None) -> tuple[int | None, int | None]:
        if not upstream:
            return None, None
        output = self.git(root, ["rev-list", "--left-right", "--count", f"{upstream}...{branch}"], check=False)
        parts = output.replace("\t", " ").split()
        if len(parts) != 2 or not all(part.isdigit() for part in parts):
            return None, None
        behind, ahead = (int(part) for part in parts)
        return ahead, behind

    def _worktree_status(self, path: str) -> dict[str, Any]:
        output = self.git(path, ["status", "--porcelain=v2", "--branch", "--untracked-files=all"])
        counts: dict[str, Any] = {"modified_count": 0, "added_count": 0, "deleted_count": 0, "untracked_count": 0, "conflict_count": 0, "changed_files": []}

        def remember(changed_path: str) -> None:
            changed_files = counts["changed_files"]
            if len(changed_path) <= 4096 and changed_path not in changed_files and len(changed_files) < MAX_CHANGED_FILES:
                changed_files.append(changed_path)

        for line in output.splitlines():
            if line.startswith("? "):
                counts["untracked_count"] += 1
                remember(line[2:])
            elif line.startswith("u "):
                counts["conflict_count"] += 1
                remember(line.split(" ", 10)[-1])
            elif line.startswith(("1 ", "2 ")):
                xy = line.split(" ", 2)[1]
                max_parts = 9 if line.startswith("2 ") else 8
                changed_path = line.split(" ", max_parts)[-1].split("\t", 1)[0]
                remember(changed_path)
                if "M" in xy or "R" in xy or "C" in xy:
                    counts["modified_count"] += 1
                if "A" in xy:
                    counts["added_count"] += 1
                if "D" in xy:
                    counts["deleted_count"] += 1
        counts["changed_files"] = sorted(counts["changed_files"])
        return counts

    def _parallel_map(self, keys: list[str], callback) -> dict[str, Any]:
        if not keys:
            return {}
        workers = min(self.max_workers, len(keys))
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="git-scan") as executor:
            values = executor.map(callback, keys)
            return dict(zip(keys, values, strict=True))

    @staticmethod
    def _age_days(value: str | None) -> float | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value)
            return (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds() / 86400
        except ValueError:
            return None
