from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from .project_service import ProjectService
from backend.app.core.path_safety import is_unc_or_device_path


class SystemActionService:
    def __init__(self, projects: ProjectService, enabled: bool = False):
        self.projects = projects
        self.enabled = enabled

    def validate_path(self, project_id: int, requested: str | None) -> Path:
        self._ensure_enabled()
        registered = self.projects.allowed_paths(project_id)
        if not registered:
            raise HTTPException(status_code=403, detail="项目没有可用的已登记目录")
        raw = str(requested) if requested else str(registered[0])
        if is_unc_or_device_path(raw):
            raise HTTPException(status_code=403, detail="不允许使用 UNC 或设备路径")
        candidate = Path(raw).expanduser().absolute()
        if not candidate.exists() or not candidate.is_dir():
            raise HTTPException(status_code=403, detail="路径必须是已登记的实际目录")
        if self._has_reparse_component(candidate):
            raise HTTPException(status_code=403, detail="不允许使用符号链接、Junction 或 Reparse Point")
        candidate_resolved = candidate.resolve(strict=True)

        allowed: set[str] = set()
        for root in registered:
            if is_unc_or_device_path(root) or not root.exists() or not root.is_dir():
                continue
            if self._has_reparse_component(root):
                continue
            allowed.add(os.path.normcase(str(root.resolve(strict=True))))
        if os.path.normcase(str(candidate_resolved)) not in allowed:
            raise HTTPException(status_code=403, detail="路径必须是已登记的项目根目录或 Worktree")
        return candidate_resolved

    def open_folder(self, project_id: int, requested: str | None) -> dict[str, Any]:
        path = self.validate_path(project_id, requested)
        self._launch(path, "folder")
        return {"accepted": True, "path": str(path)}

    def open_terminal(self, project_id: int, requested: str | None) -> dict[str, Any]:
        path = self.validate_path(project_id, requested)
        self._launch(path, "terminal")
        return {"accepted": True, "path": str(path)}

    def open_vscode(self, project_id: int, requested: str | None) -> dict[str, Any]:
        path = self.validate_path(project_id, requested)
        self._launch(path, "vscode")
        return {"accepted": True, "path": str(path)}

    @staticmethod
    def _launch(path: Path, kind: str) -> None:
        if kind == "folder":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif kind == "terminal":
            command = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "cmd.exe"
            if not command.is_file():
                raise HTTPException(status_code=503, detail="系统终端不可用")
            subprocess.Popen(
                [str(command.resolve()), "/K"],
                cwd=str(path),
                shell=False,
                creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
            )
        else:
            executable = SystemActionService._find_vscode_executable()
            if executable is None:
                raise HTTPException(status_code=503, detail="Visual Studio Code 不可用")
            subprocess.Popen([str(executable), str(path)], shell=False)

    def _ensure_enabled(self) -> None:
        if not self.enabled:
            raise HTTPException(status_code=403, detail="原生系统动作未启用")

    @staticmethod
    def _has_reparse_component(path: Path) -> bool:
        current = path
        while current != current.parent:
            try:
                metadata = os.lstat(current)
            except OSError:
                return True
            attributes = getattr(metadata, "st_file_attributes", 0)
            if current.is_symlink() or attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
                return True
            current = current.parent
        return False

    @staticmethod
    def _find_vscode_executable() -> Path | None:
        direct = shutil.which("Code.exe")
        if direct:
            return Path(direct).resolve()
        command = shutil.which("code")
        if not command:
            return None
        candidate = Path(command).resolve()
        if candidate.suffix.lower() == ".exe":
            return candidate
        installed = candidate.parent.parent / "Code.exe"
        return installed.resolve() if installed.is_file() else None
