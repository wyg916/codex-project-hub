from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import get_args


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pydantic import ValidationError

from backend.app.core.git_runner import GitCommandError
from backend.app.core.git_scanner import GitScanner
from backend.app.core.status_metadata import StatusMetadataService, UnsafeMetadataPath
from backend.app.schemas.domain import BranchStatus, BranchTask, BranchType


PHASES = ("requirement", "design", "development", "unit_test", "integration_test", "acceptance", "merge")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="更新 Git Common Dir 下的 Codex 分支状态元数据")
    result.add_argument("--repo", required=True)
    result.add_argument("--branch", required=True)
    result.add_argument("--task-name", required=True)
    result.add_argument("--objective", default="")
    result.add_argument("--branch-type", choices=get_args(BranchType), default="unknown")
    result.add_argument("--status", choices=get_args(BranchStatus), default="active")
    result.add_argument("--result", choices=("PASS", "PARTIAL", "BLOCKED", "FAIL", "UNKNOWN"), default="UNKNOWN")
    result.add_argument("--owner", default="Codex")
    result.add_argument("--task-id", default="")
    result.add_argument("--session-title", default="")
    result.add_argument("--blocker", action="append", default=[])
    result.add_argument("--next-action", action="append", default=[])
    result.add_argument("--unit", default="NOT_RUN")
    result.add_argument("--integration", default="NOT_RUN")
    result.add_argument("--e2e", default="NOT_RUN")
    for phase in PHASES:
        result.add_argument(f"--{phase.replace('_', '-')}", type=int, choices=range(101), default=0)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        repo = Path(args.repo).expanduser().resolve(strict=True)
    except OSError as exc:
        raise SystemExit("ERROR: --repo 不是有效 Git 仓库") from exc
    if not repo.is_dir():
        raise SystemExit("ERROR: --repo 不是有效 Git 仓库")
    try:
        facts = GitScanner().validate_repository(repo)
        branches = set(facts["branches"])
        common = Path(facts["git_common_dir"])
    except (GitCommandError, OSError, ValueError) as exc:
        raise SystemExit("ERROR: --repo 不是有效 Git 仓库") from exc
    if args.branch not in branches:
        raise SystemExit("ERROR: --branch 必须是现有本地分支")

    progress = {phase: getattr(args, phase) for phase in PHASES}
    try:
        task = BranchTask.model_validate(
            {
                "branch_type": args.branch_type,
                "task_name": args.task_name,
                "objective": args.objective,
                "codex_task_id": args.task_id,
                "codex_session_title": args.session_title,
                "owner": args.owner,
                "status": args.status,
                "phase": next((phase for phase in reversed(PHASES) if progress[phase] > 0), ""),
                "result": args.result,
                "progress_mode": "weighted",
                "phase_progress": progress,
                "tests": {"unit": args.unit, "integration": args.integration, "e2e": args.e2e},
                "blockers": args.blocker,
                "next_actions": args.next_action,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    except ValidationError as exc:
        raise SystemExit("ERROR: 参数不符合状态元数据 schema") from exc

    metadata = StatusMetadataService()
    try:
        metadata.update_branch(
            common,
            args.branch,
            task,
            project_defaults={
                "display_name": Path(facts["repo_path"]).name,
                "canonical_worktree": facts["canonical_worktree"],
                "main_branch": facts["main_branch"],
                "integration_branch": "",
                "rc_branch": "",
            },
        )
    except (OSError, ValueError, ValidationError, UnsafeMetadataPath) as exc:
        raise SystemExit("ERROR: 状态元数据写入被安全策略拒绝") from exc
    print(f"STATUS_UPDATE=PASS branch={args.branch}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
