from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app


def git(cwd: Path, *args: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", shell=False,
    )
    if check and completed.returncode != 0:
        raise RuntimeError(completed.stderr or completed.stdout)
    return completed.stdout.strip()


def configure_repo(path: Path) -> None:
    git(path, "config", "user.name", "Codex Test")
    git(path, "config", "user.email", "codex-test@example.invalid")


@pytest.fixture()
def git_repo(tmp_path: Path) -> dict[str, Path]:
    repo = tmp_path / "中文 Git 仓库"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    configure_repo(repo)
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    git(repo, "add", "README.md")
    git(repo, "commit", "-m", "initial")

    git(repo, "branch", "feat/dashboard")
    worktree = tmp_path / "功能 工作树"
    git(repo, "worktree", "add", str(worktree), "feat/dashboard")
    configure_repo(worktree)
    (worktree / "feature.txt").write_text("feature\n", encoding="utf-8")
    git(worktree, "add", "feature.txt")
    git(worktree, "commit", "-m", "feature commit")
    (worktree / "feature.txt").write_text("feature modified\n", encoding="utf-8")
    (worktree / "未跟踪.txt").write_text("untracked\n", encoding="utf-8")

    origin = tmp_path / "origin.git"
    origin.mkdir()
    git(origin, "init", "--bare")
    git(origin, "symbolic-ref", "HEAD", "refs/heads/main")
    git(repo, "remote", "add", "origin", str(origin))
    git(repo, "push", "-u", "origin", "main")
    git(repo, "push", "-u", "origin", "feat/dashboard")

    peer = tmp_path / "peer"
    git(tmp_path, "clone", str(origin), str(peer))
    configure_repo(peer)
    (peer / "remote.txt").write_text("remote\n", encoding="utf-8")
    git(peer, "add", "remote.txt")
    git(peer, "commit", "-m", "remote commit")
    git(peer, "push", "origin", "main")
    (repo / "local.txt").write_text("local\n", encoding="utf-8")
    git(repo, "add", "local.txt")
    git(repo, "commit", "-m", "local commit")
    git(repo, "fetch", "origin")
    git(repo, "branch", "merged/example")
    git(repo, "branch", "fix/demo")
    return {"repo": repo, "worktree": worktree, "origin": origin}


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("CPC_DISABLE_BACKGROUND", "1")
    monkeypatch.setenv("CPC_DISABLE_SYSTEM_ACTIONS", "1")
    settings = Settings(
        data_dir=tmp_path / "app-data",
        database_path=tmp_path / "app-data" / "test.db",
        frontend_dist=tmp_path / "dist",
        scan_interval_seconds=1,
        allowed_hosts=("127.0.0.1", "localhost", "testserver", "[::1]"),
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client
