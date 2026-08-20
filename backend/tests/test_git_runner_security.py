from __future__ import annotations

import io
import subprocess
from pathlib import Path

import pytest

from backend.app.core import git_runner
from backend.app.core.git_runner import GitCommandError, _read_limited, redact, run_git


def test_read_only_whitelist_rejects_options_and_mutations(tmp_path: Path) -> None:
    with pytest.raises(GitCommandError):
        run_git(tmp_path, ["status", "--porcelain=v2", "--branch", "--no-renames"])
    with pytest.raises(GitCommandError):
        run_git(tmp_path, ["push", "origin", "main"])
    with pytest.raises(GitCommandError):
        run_git(tmp_path, ["log", "--config-env=core.fsmonitor=ATTACK", "--max-count=1", "--format=%H"])


def test_runner_uses_fixed_git_safe_globals_clean_env_and_bounded_pipes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    observed: dict[str, object] = {}

    class FakeProcess:
        stdout = io.BytesIO(b"result\n")
        stderr = io.BytesIO(b"")

        def wait(self, timeout=None):
            observed["timeout"] = timeout
            return 0

        def kill(self):
            raise AssertionError("process should not be killed")

    def fake_popen(args, **kwargs):
        observed["args"] = args
        observed.update(kwargs)
        return FakeProcess()

    monkeypatch.setenv("GIT_DIR", str(tmp_path / "attacker"))
    monkeypatch.setenv("GIT_WORK_TREE", str(tmp_path / "worktree"))
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.fsmonitor")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "attack.exe")
    monkeypatch.setenv("GIT_TRACE", str(tmp_path / "trace.log"))
    monkeypatch.setenv("GIT_NAMESPACE", "attacker")
    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    assert run_git(tmp_path, ["rev-parse", "--show-toplevel"]) == "result"
    args = observed["args"]
    assert args[0] == git_runner.git_executable()
    assert args[1:7] == ["--no-pager", "--no-optional-locks", "-c", "core.fsmonitor=false", "-c", "core.quotepath=false"]
    assert args[7:11] == ["-c", "color.ui=false", "-c", "column.ui=never"]
    assert ["-c", "log.showSignature=false"] == args[11:13]
    assert ["-c", "log.mailmap=false"] == args[13:15]
    assert "core.pager=cat" not in args
    environment = observed["env"]
    assert environment["GIT_OPTIONAL_LOCKS"] == "0"
    assert environment["GIT_TERMINAL_PROMPT"] == "0"
    assert "GIT_DIR" not in environment
    assert "GIT_WORK_TREE" not in environment
    assert "GIT_CONFIG_COUNT" not in environment
    assert "GIT_TRACE" not in environment
    assert "GIT_NAMESPACE" not in environment
    assert observed["shell"] is False


def test_redaction_covers_protocol_userinfo_and_sensitive_query_values() -> None:
    github_token = "github" + "_pat_" + ("A" * 32)
    jwt = ".".join(("eyJ" + ("a" * 12), "b" * 16, "c" * 16))
    source = (
        "ssh://alice:password@example.test/repo "
        "ftp://bob:secret@example.test/repo?password=hunter2&api_key=abc "
        "https://example.test/repo?token=xyz#token=fragment-secret "
        f"https://example.test/{github_token}/{jwt} Authorization: Bearer token-value"
    )
    result = redact(source)
    for secret in (
        "alice:password",
        "bob:secret",
        "hunter2",
        "abc",
        "xyz",
        "fragment-secret",
        github_token,
        jwt,
        "token-value",
    ):
        assert secret not in result
    assert result.count("<REDACTED>") >= 6


def test_limited_reader_drains_but_retains_only_limit() -> None:
    data, truncated = _read_limited(io.BytesIO(b"0123456789"), 4)
    assert data == b"0123"
    assert truncated is True
