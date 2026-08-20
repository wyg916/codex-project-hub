from __future__ import annotations

import os
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path
from typing import BinaryIO


MAX_GIT_OUTPUT_BYTES = 4 * 1024 * 1024
_LONG_REF_FORMAT = (
    "%(refname:short)%00%(objectname)%00%(upstream:short)%00%(subject)%00"
    "%(authorname)%00%(authordate:iso-strict)"
)
_SENSITIVE_QUERY_KEY = (
    r"token|access_token|refresh_token|auth|authorization|password|passwd|pwd|secret|"
    r"client_secret|api_key|apikey|key|credential"
)


class GitCommandError(RuntimeError):
    pass


def redact(value: str) -> str:
    value = re.sub(
        r"(?i)([a-z][a-z0-9+.-]*://)[^/@\s?#]+@",
        r"\1<REDACTED>@",
        value,
    )
    value = re.sub(
        r"(?i)(?<![\w@])[^\s/:@]+:[^\s@]+@(?=[^\s/:@]+[:/])",
        "<REDACTED>@",
        value,
    )
    value = re.sub(
        rf"(?i)([?&#](?:{_SENSITIVE_QUERY_KEY})=)[^&#\s]+",
        r"\1<REDACTED>",
        value,
    )
    value = re.sub(r"(?i)\b(authorization\s*:\s*(?:bearer|basic)\s+)[^\s]+", r"\1<REDACTED>", value)
    value = re.sub(r"(?i)\bgithub_pat_[a-z0-9_]{20,}\b", "<REDACTED_TOKEN>", value)
    value = re.sub(r"(?i)\bgh[pousr]_[a-z0-9]{20,}\b", "<REDACTED_TOKEN>", value)
    value = re.sub(r"\beyJ[a-zA-Z0-9_-]{8,}\.[a-zA-Z0-9_-]{8,}\.[a-zA-Z0-9_-]{8,}\b", "<REDACTED_TOKEN>", value)
    value = re.sub(r"(?i)\bxox[baprs]-[a-z0-9-]{20,}\b", "<REDACTED_TOKEN>", value)
    return value


@lru_cache(maxsize=1)
def git_executable() -> str:
    candidate = shutil.which("git.exe" if os.name == "nt" else "git")
    if not candidate:
        raise GitCommandError("Git executable is unavailable")
    path = Path(candidate).resolve(strict=True)
    if not path.is_file() or (os.name == "nt" and path.suffix.lower() != ".exe"):
        raise GitCommandError("Git executable is unavailable")
    return str(path)


def _valid_ref(value: str) -> bool:
    return (
        bool(value)
        and len(value) <= 1024
        and not value.startswith("-")
        and not value.endswith((".", "/"))
        and ".." not in value
        and "@{" not in value
        and not any(ord(character) <= 32 or ord(character) == 127 or character in "~^:?*[\\" for character in value)
    )


def _valid_revision(value: str) -> bool:
    for separator in ("...", ".."):
        if separator in value:
            parts = value.split(separator)
            return len(parts) == 2 and all(_valid_ref(part) for part in parts)
    return _valid_ref(value)


def _validate_read_only_command(args: list[str]) -> None:
    if not args or len(args) > 16 or any(len(arg) > 4096 or "\x00" in arg or "\r" in arg or "\n" in arg for arg in args):
        raise GitCommandError("Git command is not permitted")
    command, rest = args[0], args[1:]
    permitted = False

    if command == "rev-parse":
        permitted = rest in (["--show-toplevel"], ["--git-common-dir"], ["--verify", "HEAD"])
    elif command == "remote":
        permitted = rest == ["get-url", "origin"]
    elif command == "worktree":
        permitted = rest == ["list", "--porcelain"]
    elif command == "for-each-ref":
        permitted = len(rest) == 2 and rest[0] in {
            "--format=%(refname:short)",
            f"--format={_LONG_REF_FORMAT}",
        } and rest[1] == "refs/heads"
    elif command == "symbolic-ref":
        permitted = rest in (
            ["refs/remotes/origin/HEAD"],
            ["--short", "HEAD"],
        )
    elif command == "merge-base":
        permitted = len(rest) == 2 and all(_valid_ref(value) for value in rest)
    elif command == "branch":
        permitted = (
            len(rest) == 3
            and rest[:2] == ["--format=%(refname:short)", "--merged"]
            and _valid_ref(rest[2])
        )
    elif command == "rev-list":
        permitted = (
            len(rest) == 2
            and rest[0] == "--count"
            and _valid_revision(rest[1])
        ) or (
            len(rest) == 3
            and rest[:2] == ["--left-right", "--count"]
            and rest[2].count("...") == 1
            and all(_valid_ref(value) for value in rest[2].split("..."))
        )
    elif command == "status":
        permitted = rest == ["--porcelain=v2", "--branch", "--untracked-files=all"]
    elif command == "log":
        permitted = (
            len(rest) == 3
            and _valid_revision(rest[0])
            and re.fullmatch(r"--max-count=([1-9]|[1-9][0-9]{1,2})", rest[1]) is not None
            and rest[2].startswith("--format=")
            and len(rest[2]) <= 2048
        )

    if not permitted:
        raise GitCommandError("Git command is not permitted")


def _sanitized_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for key in list(environment):
        if key.upper().startswith("GIT_"):
            environment.pop(key, None)
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    environment["GIT_TERMINAL_PROMPT"] = "0"
    return environment


def _read_limited(stream: BinaryIO, limit: int) -> tuple[bytes, bool]:
    retained = bytearray()
    truncated = False
    while True:
        chunk = stream.read(64 * 1024)
        if not chunk:
            break
        remaining = limit - len(retained)
        if remaining > 0:
            retained.extend(chunk[:remaining])
        if len(chunk) > remaining:
            truncated = True
    return bytes(retained), truncated


def run_git(cwd: str | Path, args: list[str], timeout: float = 8.0, check: bool = True) -> str:
    _validate_read_only_command(args)
    command = [
        git_executable(),
        "--no-pager",
        "--no-optional-locks",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.quotepath=false",
        "-c",
        "color.ui=false",
        "-c",
        "column.ui=never",
        "-c",
        "log.showSignature=false",
        "-c",
        "log.mailmap=false",
        *args,
    ]
    try:
        process = subprocess.Popen(
            command,
            cwd=str(Path(cwd).resolve(strict=True)),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=_sanitized_environment(),
            shell=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, RuntimeError) as exc:
        raise GitCommandError("Git command could not be started") from exc

    assert process.stdout is not None and process.stderr is not None
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="git-output") as executor:
        stdout_future = executor.submit(_read_limited, process.stdout, MAX_GIT_OUTPUT_BYTES)
        stderr_future = executor.submit(_read_limited, process.stderr, MAX_GIT_OUTPUT_BYTES)
        try:
            returncode = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            process.kill()
            process.wait()
            stdout_future.result()
            stderr_future.result()
            raise GitCommandError("Git command timed out") from exc
        stdout_bytes, stdout_truncated = stdout_future.result()
        stderr_bytes, stderr_truncated = stderr_future.result()

    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace")
    if stdout_truncated or stderr_truncated:
        raise GitCommandError("Git command output exceeded the safety limit")
    if check and returncode != 0:
        message = redact(stderr.strip() or stdout.strip() or "Git command failed")
        raise GitCommandError(message)
    return redact(stdout.rstrip("\r\n"))
