from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from backend.tests.conftest import configure_repo, git


def test_status_script_writes_common_dir_without_dirtying_worktree(tmp_path: Path) -> None:
    repo = tmp_path / "script-repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    configure_repo(repo)
    (repo / "README.md").write_text("base", encoding="utf-8")
    git(repo, "add", "README.md")
    git(repo, "commit", "-m", "base")
    script = Path(__file__).resolve().parents[2] / "scripts" / "update-codex-status.py"
    completed = subprocess.run(
        [sys.executable, str(script), "--repo", str(repo), "--branch", "main", "--task-name", "脚本测试", "--status", "validating", "--result", "PARTIAL", "--development", "80", "--next-action", "继续验收"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", shell=False,
    )
    assert completed.returncode == 0, completed.stderr
    common = Path(git(repo, "rev-parse", "--git-common-dir"))
    path = (repo / common / "codex-dashboard" / "status.json").resolve()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["branches"]["main"]["phase_progress"]["development"] == 80
    assert payload["branches"]["main"]["tests"]["unit"] == "NOT_RUN"
    assert git(repo, "status", "--porcelain") == ""


def test_status_script_rejects_invalid_status(tmp_path: Path) -> None:
    repo = tmp_path / "invalid-status-repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    configure_repo(repo)
    (repo / "README.md").write_text("base", encoding="utf-8")
    git(repo, "add", "README.md")
    git(repo, "commit", "-m", "base")
    script = Path(__file__).resolve().parents[2] / "scripts" / "update-codex-status.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--repo",
            str(repo),
            "--branch",
            "main",
            "--task-name",
            "invalid",
            "--status",
            "not-a-status",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
    )
    assert completed.returncode != 0
    assert not (repo / ".git" / "codex-dashboard" / "status.json").exists()


def test_status_script_uses_detected_non_main_default_branch(tmp_path: Path) -> None:
    repo = tmp_path / "trunk-repo"
    repo.mkdir()
    git(repo, "init", "-b", "trunk")
    configure_repo(repo)
    (repo / "README.md").write_text("base", encoding="utf-8")
    git(repo, "add", "README.md")
    git(repo, "commit", "-m", "base")
    script = Path(__file__).resolve().parents[2] / "scripts" / "update-codex-status.py"
    completed = subprocess.run(
        [sys.executable, str(script), "--repo", str(repo), "--branch", "trunk", "--task-name", "trunk task"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads((repo / ".git" / "codex-dashboard" / "status.json").read_text(encoding="utf-8"))
    assert payload["project"]["main_branch"] == "trunk"
    assert payload["project"]["canonical_worktree"] == str(repo.resolve())


def test_status_script_from_linked_worktree_subdirectory_uses_main_worktree_facts(
    git_repo: dict[str, Path],
) -> None:
    subdirectory = git_repo["worktree"] / "nested"
    subdirectory.mkdir()
    script = Path(__file__).resolve().parents[2] / "scripts" / "update-codex-status.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--repo",
            str(subdirectory),
            "--branch",
            "feat/dashboard",
            "--task-name",
            "linked worktree task",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(
        (git_repo["repo"] / ".git" / "codex-dashboard" / "status.json").read_text(encoding="utf-8")
    )
    assert payload["project"]["canonical_worktree"] == str(git_repo["repo"].resolve())
    assert payload["project"]["display_name"] == git_repo["repo"].name


def test_status_script_rejects_linked_dashboard(tmp_path: Path) -> None:
    repo = tmp_path / "linked-dashboard-repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    configure_repo(repo)
    (repo / "README.md").write_text("base", encoding="utf-8")
    git(repo, "add", "README.md")
    git(repo, "commit", "-m", "base")
    outside = tmp_path / "outside"
    outside.mkdir()
    dashboard = repo / ".git" / "codex-dashboard"
    try:
        dashboard.symlink_to(outside, target_is_directory=True)
    except OSError:
        junction = subprocess.run(
            [
                "cmd.exe",
                "/D",
                "/C",
                "mklink",
                "/J",
                str(dashboard),
                str(outside),
            ],
            capture_output=True,
            text=True,
            shell=False,
        )
        if junction.returncode != 0:
            pytest.skip("directory links are unavailable on this Windows host")
    script = Path(__file__).resolve().parents[2] / "scripts" / "update-codex-status.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--repo",
            str(repo),
            "--branch",
            "main",
            "--task-name",
            "must-not-write",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
    )
    assert completed.returncode != 0
    assert not (outside / "status.json").exists()


def test_two_status_cli_processes_preserve_both_branches(tmp_path: Path) -> None:
    repo = tmp_path / "concurrent-cli-repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    configure_repo(repo)
    (repo / "README.md").write_text("base", encoding="utf-8")
    git(repo, "add", "README.md")
    git(repo, "commit", "-m", "base")
    git(repo, "branch", "feat/one")
    git(repo, "branch", "feat/two")
    script = Path(__file__).resolve().parents[2] / "scripts" / "update-codex-status.py"
    processes = [
        subprocess.Popen(
            [
                sys.executable,
                str(script),
                "--repo",
                str(repo),
                "--branch",
                branch,
                "--task-name",
                branch,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
        )
        for branch in ("feat/one", "feat/two")
    ]
    results = [process.communicate(timeout=15) for process in processes]
    assert [process.returncode for process in processes] == [0, 0], results
    path = repo / ".git" / "codex-dashboard" / "status.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert set(payload["branches"]) == {"feat/one", "feat/two"}
