from __future__ import annotations

import json
import os
import shutil
import stat
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from pydantic import ValidationError

from backend.app.schemas.domain import BranchTask, StatusMetadata, weighted_progress
from backend.app.core.path_safety import is_unc_or_device_path


MAX_STATUS_BYTES = 1024 * 1024
MAX_STATUS_BACKUPS = 5
METADATA_LOCK_TIMEOUT_SECONDS = 5.0


class UnsafeMetadataPath(ValueError):
    pass


class StatusMetadataService:
    def metadata_path(self, git_common_dir: str | Path) -> Path:
        return self._safe_path(git_common_dir, "status.json")

    def read(self, git_common_dir: str | Path) -> dict[str, Any]:
        try:
            path = self.metadata_path(git_common_dir)
        except (OSError, UnsafeMetadataPath):
            return {"maintained": False, "data": None, "error": "状态文件路径不安全", "path": None}
        if not path.exists():
            return {"maintained": False, "data": None, "error": None, "path": str(path)}
        try:
            if path.stat().st_size > MAX_STATUS_BYTES:
                raise ValueError("status metadata exceeds size limit")
            raw = json.loads(path.read_text(encoding="utf-8"))
            model = StatusMetadata.model_validate(raw)
            data = model.model_dump(mode="json")
            for task in data["branches"].values():
                task["progress"] = weighted_progress(task)
            return {"maintained": True, "data": data, "error": None, "path": str(path)}
        except (OSError, ValueError, json.JSONDecodeError, ValidationError):
            return {
                "maintained": True,
                "data": None,
                "error": "状态文件不可解析",
                "path": str(path),
            }

    def write(self, git_common_dir: str | Path, payload: dict[str, Any] | StatusMetadata) -> dict[str, Any]:
        model = payload if isinstance(payload, StatusMetadata) else StatusMetadata.model_validate(payload)
        with self._metadata_lock(git_common_dir):
            existing = self.read(git_common_dir)
            if existing["error"]:
                raise ValueError("状态文件已损坏，请先人工修复；系统不会覆盖原文件")
            return self._write_unlocked(git_common_dir, model)

    def _write_unlocked(self, git_common_dir: str | Path, model: StatusMetadata) -> dict[str, Any]:
        path = self._safe_path(git_common_dir, "status.json", create_dashboard=True)
        encoded = json.dumps(model.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"
        if len(encoded.encode("utf-8")) > MAX_STATUS_BYTES:
            raise ValueError("状态文件超过安全大小限制")
        if path.exists():
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            backup = self._safe_path(git_common_dir, f"status.{timestamp}.bak.json", create_dashboard=True)
            shutil.copy2(path, backup)
            self._prune_backups(path.parent)
        handle, temp_name = tempfile.mkstemp(prefix="status.", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            target = self._safe_path(git_common_dir, "status.json", create_dashboard=True)
            os.replace(temp_name, target)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        return self.read(git_common_dir)

    def update_branch(
        self,
        git_common_dir: str | Path,
        branch_name: str,
        task: BranchTask,
        project_defaults: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._metadata_lock(git_common_dir):
            existing = self.read(git_common_dir)
            if existing["error"]:
                raise ValueError("状态文件已损坏，请先人工修复；系统不会覆盖原文件")
            if existing["data"]:
                payload = existing["data"]
                for value in payload["branches"].values():
                    value.pop("progress", None)
            else:
                payload = {
                    "schema_version": 1,
                    "project": project_defaults
                    or {"display_name": "", "canonical_worktree": "", "main_branch": "main"},
                    "branches": {},
                }
            payload["branches"][branch_name] = task.model_dump(mode="json")
            model = StatusMetadata.model_validate(payload)
            return self._write_unlocked(git_common_dir, model)

    def _safe_path(self, git_common_dir: str | Path, filename: str, create_dashboard: bool = False) -> Path:
        if filename not in {"status.json", "status.lock"} and not (
            filename.startswith("status.") and filename.endswith(".bak.json")
        ):
            raise UnsafeMetadataPath("unsupported metadata filename")
        if is_unc_or_device_path(git_common_dir):
            raise UnsafeMetadataPath("remote metadata path is not permitted")
        raw_common = Path(git_common_dir).expanduser().absolute()
        if self._is_reparse_point(raw_common):
            raise UnsafeMetadataPath("unsafe git common dir")
        common = raw_common.resolve(strict=True)
        if not common.is_dir():
            raise UnsafeMetadataPath("invalid git common dir")

        dashboard = common / "codex-dashboard"
        if dashboard.exists() or dashboard.is_symlink():
            if self._is_reparse_point(dashboard):
                raise UnsafeMetadataPath("unsafe dashboard directory")
        elif create_dashboard:
            dashboard.mkdir(mode=0o700, exist_ok=True)

        if dashboard.exists():
            if self._is_reparse_point(dashboard):
                raise UnsafeMetadataPath("unsafe dashboard directory")
            resolved_dashboard = dashboard.resolve(strict=True)
            if resolved_dashboard.parent != common:
                raise UnsafeMetadataPath("dashboard escaped git common dir")
        else:
            resolved_dashboard = dashboard

        target = resolved_dashboard / filename
        if target.exists() or target.is_symlink():
            if self._is_reparse_point(target):
                raise UnsafeMetadataPath("unsafe metadata file")
            resolved_target = target.resolve(strict=True)
            if resolved_target.parent != resolved_dashboard:
                raise UnsafeMetadataPath("metadata escaped dashboard directory")
            return resolved_target
        if target.parent != resolved_dashboard:
            raise UnsafeMetadataPath("invalid metadata target")
        return target

    @contextmanager
    def _metadata_lock(self, git_common_dir: str | Path) -> Iterator[None]:
        path = self._safe_path(git_common_dir, "status.lock", create_dashboard=True)
        deadline = time.monotonic() + METADATA_LOCK_TIMEOUT_SECONDS
        with path.open("a+b") as stream:
            stream.seek(0, os.SEEK_END)
            if stream.tell() == 0:
                stream.write(b"\0")
                stream.flush()
                os.fsync(stream.fileno())
            acquired = False
            while not acquired:
                stream.seek(0)
                try:
                    if os.name == "nt":
                        import msvcrt

                        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                except OSError as exc:
                    if time.monotonic() >= deadline:
                        raise ValueError("状态元数据写锁超时") from exc
                    time.sleep(0.05)
            try:
                yield
            finally:
                stream.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _is_reparse_point(path: Path) -> bool:
        if path.is_symlink():
            return True
        try:
            metadata = os.lstat(path)
        except FileNotFoundError:
            return False
        attributes = getattr(metadata, "st_file_attributes", 0)
        return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))

    def _prune_backups(self, dashboard: Path) -> None:
        backups = sorted(
            dashboard.glob("status.*.bak.json"),
            key=lambda candidate: candidate.name,
            reverse=True,
        )
        for stale in backups[MAX_STATUS_BACKUPS:]:
            if self._is_reparse_point(stale) or not stale.is_file():
                raise UnsafeMetadataPath("unsafe status backup")
            stale.unlink()
