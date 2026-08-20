from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fastapi import HTTPException

from backend.app.services.system_actions import SystemActionService


class RegisteredProjects:
    def __init__(self, paths: list[Path]) -> None:
        self.paths = paths

    def allowed_paths(self, project_id: int) -> list[Path]:
        assert project_id == 1
        return self.paths


def test_system_actions_are_disabled_by_default(tmp_path: Path) -> None:
    service = SystemActionService(RegisteredProjects([tmp_path]))  # type: ignore[arg-type]
    with pytest.raises(HTTPException) as caught:
        service.open_folder(1, str(tmp_path))
    assert caught.value.status_code == 403
    assert "未启用" in str(caught.value.detail)


def test_only_registered_real_directory_is_allowed(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    child = root / "child"
    child.mkdir()
    file_path = root / "file.txt"
    file_path.write_text("content", encoding="utf-8")
    service = SystemActionService(RegisteredProjects([root]), enabled=True)  # type: ignore[arg-type]

    assert service.validate_path(1, str(root)) == root.resolve()
    for value in (str(child), str(file_path), str(tmp_path), r"\\server\share\repo"):
        with pytest.raises(HTTPException) as caught:
            service.validate_path(1, value)
        assert caught.value.status_code == 403


def test_reparse_or_symlink_root_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    service = SystemActionService(RegisteredProjects([root]), enabled=True)  # type: ignore[arg-type]
    monkeypatch.setattr(service, "_has_reparse_component", lambda path: path == root)
    with pytest.raises(HTTPException) as caught:
        service.validate_path(1, str(root))
    assert caught.value.status_code == 403


def test_terminal_path_is_only_used_as_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dangerous = tmp_path / "repo&whoami"
    dangerous.mkdir()
    windows = tmp_path / "Windows"
    command = windows / "System32" / "cmd.exe"
    command.parent.mkdir(parents=True)
    command.write_bytes(b"")
    observed: dict[str, object] = {}

    def fake_popen(args, **kwargs):
        observed["args"] = args
        observed.update(kwargs)
        return object()

    monkeypatch.setenv("SystemRoot", str(windows))
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    SystemActionService._launch(dangerous, "terminal")

    assert observed["args"] == [str(command.resolve()), "/K"]
    assert observed["cwd"] == str(dangerous)
    assert str(dangerous) not in observed["args"]
    assert observed["shell"] is False
