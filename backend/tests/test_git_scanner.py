from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from backend.app.core.git_runner import GitCommandError
from backend.app.core.git_scanner import MAX_BRANCHES, GitScanner
from backend.app.core.worktree_scanner import MAX_WORKTREES, WorktreeScanner
from backend.tests.conftest import configure_repo, git


def project(repo: Path) -> dict[str, object]:
    facts = GitScanner().validate_repository(repo)
    return {
        "id": 1,
        "repo_path": facts["repo_path"],
        "canonical_worktree": facts["canonical_worktree"],
        "git_common_dir": facts["git_common_dir"],
        "main_branch": "main",
        "integration_branch": None,
        "rc_branch": None,
    }


def test_scans_chinese_repo_worktrees_dirty_and_sync(git_repo: dict[str, Path]) -> None:
    scanner = GitScanner()
    facts = scanner.validate_repository(git_repo["worktree"])
    assert facts["repo_path"] == str(git_repo["repo"].resolve())
    assert len(facts["worktrees"]) == 2
    snapshot = scanner.scan_project(project(git_repo["repo"]))
    branches = {item["name"]: item for item in snapshot["branches"]}
    assert {"main", "feat/dashboard", "fix/demo", "merged/example"} <= set(branches)
    assert branches["feat/dashboard"]["modified_count"] == 1
    assert branches["feat/dashboard"]["untracked_count"] == 1
    assert {"feature.txt", "未跟踪.txt"} <= set(branches["feat/dashboard"]["changed_files"])
    assert branches["main"]["ahead"] == 1
    assert branches["main"]["behind"] == 1
    assert branches["merged/example"]["is_merged_to_main"] is True
    assert snapshot["remote_url"] == str(git_repo["origin"])


def test_detached_worktree_dirty_status_is_preserved(git_repo: dict[str, Path], tmp_path: Path) -> None:
    detached = tmp_path / "detached-worktree"
    git(git_repo["repo"], "worktree", "add", "--detach", str(detached), "HEAD")
    (detached / "detached-untracked.txt").write_text("dirty\n", encoding="utf-8")

    snapshot = GitScanner().scan_project(project(git_repo["repo"]))
    item = next(worktree for worktree in snapshot["worktrees"] if worktree["path"] == str(detached.resolve()))

    assert item["branch"] == "DETACHED"
    assert item["untracked_count"] == 1
    assert item["changed_files"] == ["detached-untracked.txt"]


def test_merged_branch_names_ignore_forced_color_config(git_repo: dict[str, Path]) -> None:
    git(git_repo["repo"], "config", "color.branch", "always")
    merged = GitScanner()._merged_branches(git_repo["repo"], "main")
    assert "merged/example" in merged
    assert all("\x1b" not in branch for branch in merged)


def test_branch_limit_fails_before_enrichment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    scanner = GitScanner()
    fields = "\x00".join(("branch-{0}", "a" * 40, "", "subject", "author", "2026-01-01T00:00:00+00:00"))
    output = "\n".join(fields.format(index) for index in range(MAX_BRANCHES + 1))
    monkeypatch.setattr(scanner, "git", lambda *_args, **_kwargs: output)
    with pytest.raises(GitCommandError, match="branch limit"):
        scanner._branch_records(tmp_path)


def test_worktree_limit_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.app.core import worktree_scanner

    output = "\n\n".join(
        f"worktree {tmp_path / f'worktree-{index}'}\nHEAD {'a' * 40}\nbranch refs/heads/branch-{index}"
        for index in range(MAX_WORKTREES + 1)
    )
    monkeypatch.setattr(worktree_scanner, "run_git", lambda *_args, **_kwargs: output)
    with pytest.raises(GitCommandError, match="worktree limit"):
        WorktreeScanner().scan(tmp_path)


@pytest.mark.parametrize(
    "unsafe",
    [r"\\server\share\repo", "//server/share/repo", r"\\?\C:\repo", r"\\.\pipe\repo"],
)
def test_repository_identity_rejects_remote_or_device_path_before_git(
    unsafe: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    scanner = GitScanner()
    monkeypatch.setattr(scanner, "git", lambda *_args, **_kwargs: pytest.fail("Git must not run for unsafe paths"))

    with pytest.raises(ValueError, match="UNC"):
        scanner.repository_identity(unsafe)


def test_repository_identity_rejects_unsafe_git_toplevel_before_resolve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scanner = GitScanner()
    monkeypatch.setattr(scanner, "git", lambda *_args, **_kwargs: r"\\server\share\repo")

    with pytest.raises(ValueError, match="UNC"):
        scanner.repository_identity(tmp_path)


def test_worktree_metadata_rejects_unc_before_path_resolution(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from backend.app.core import worktree_scanner

    monkeypatch.setattr(
        worktree_scanner,
        "run_git",
        lambda *_args, **_kwargs: "worktree \\\\server\\share\\repo\nHEAD 0000000\nbranch refs/heads/main\n",
    )

    with pytest.raises(GitCommandError, match="remote or device"):
        WorktreeScanner().scan(tmp_path)


@pytest.mark.parametrize(
    ("method", "args"),
    [
        ("_merged_branches", (Path("repo"), "main")),
        ("_worktree_status", ("repo",)),
    ],
)
def test_required_git_facts_fail_scan_instead_of_fabricating_clean_state(
    method: str,
    args: tuple[object, ...],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scanner = GitScanner()
    monkeypatch.setattr(
        scanner,
        "git",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(GitCommandError("required fact failed")),
    )
    with pytest.raises(GitCommandError, match="required fact failed"):
        getattr(scanner, method)(*args)


def test_current_branch_distinguishes_detached_head_from_command_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "detached"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    configure_repo(repo)
    (repo / "a.txt").write_text("a", encoding="utf-8")
    git(repo, "add", "a.txt")
    git(repo, "commit", "-m", "base")
    git(repo, "checkout", "--detach")
    assert GitScanner()._current_branch(repo) == "DETACHED"

    scanner = GitScanner()

    def failed_git(_cwd, args, check=True):
        if args == ["symbolic-ref", "--short", "HEAD"]:
            return ""
        raise GitCommandError("head verification failed")

    monkeypatch.setattr(scanner, "git", failed_git)
    with pytest.raises(GitCommandError, match="head verification failed"):
        scanner._current_branch(repo)


def test_scan_uses_porcelain_conflict_facts_without_duplicate_ls_files(git_repo: dict[str, Path], monkeypatch) -> None:
    scanner = GitScanner()
    original = scanner.git
    commands: list[tuple[str, ...]] = []

    def recorded(cwd, args, check=True):
        commands.append(tuple(args))
        return original(cwd, args, check)

    monkeypatch.setattr(scanner, "git", recorded)
    scanner.scan_project(project(git_repo["repo"]))
    assert not any("ls-files" in command for command in commands)
    assert any("status" in command and "--porcelain=v2" in command for command in commands)


def test_scan_reports_untracked_files_despite_repo_config(git_repo: dict[str, Path]) -> None:
    git(git_repo["worktree"], "config", "status.showUntrackedFiles", "no")
    snapshot = GitScanner().scan_project(project(git_repo["repo"]))
    feature = next(branch for branch in snapshot["branches"] if branch["name"] == "feat/dashboard")
    assert feature["untracked_count"] == 1
    assert "未跟踪.txt" in feature["changed_files"]


def test_repository_without_origin_is_supported(tmp_path: Path) -> None:
    repo = tmp_path / "no-origin"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    configure_repo(repo)
    (repo / "a.txt").write_text("a", encoding="utf-8")
    git(repo, "add", "a.txt")
    git(repo, "commit", "-m", "first")
    facts = GitScanner().validate_repository(repo)
    assert facts["remote_url"] is None


def test_conflict_and_prunable_worktree_are_reported(tmp_path: Path) -> None:
    repo = tmp_path / "conflict-repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    configure_repo(repo)
    (repo / "same.txt").write_text("base\n", encoding="utf-8")
    git(repo, "add", "same.txt")
    git(repo, "commit", "-m", "base")
    git(repo, "checkout", "-b", "fix/conflict")
    (repo / "same.txt").write_text("feature\n", encoding="utf-8")
    git(repo, "commit", "-am", "feature")
    git(repo, "checkout", "main")
    (repo / "same.txt").write_text("main\n", encoding="utf-8")
    git(repo, "commit", "-am", "main")
    git(repo, "merge", "fix/conflict", check=False)
    snapshot = GitScanner().scan_project(project(repo))
    main = next(item for item in snapshot["branches"] if item["name"] == "main")
    assert main["conflict_count"] == 1

    clean_repo = tmp_path / "prunable-repo"
    clean_repo.mkdir()
    git(clean_repo, "init", "-b", "main")
    configure_repo(clean_repo)
    (clean_repo / "a").write_text("a", encoding="utf-8")
    git(clean_repo, "add", "a")
    git(clean_repo, "commit", "-m", "a")
    git(clean_repo, "branch", "feature/prunable")
    missing = tmp_path / "missing-worktree"
    git(clean_repo, "worktree", "add", str(missing), "feature/prunable")
    shutil.rmtree(missing)
    worktrees = GitScanner().validate_repository(clean_repo)["worktrees"]
    assert any(not item["path_exists"] and item["is_prunable"] for item in worktrees)
