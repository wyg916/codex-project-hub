from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def git(cwd: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=15, shell=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
    return completed.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a local Chinese-path Git demo repository and Worktree")
    parser.add_argument("--target", default=str(ROOT / "data" / "demo-repositories" / "新能源中文演示仓库"))
    args = parser.parse_args()
    repo = Path(args.target).expanduser().resolve()
    worktree = repo.with_name(f"{repo.name}-功能Worktree")
    if repo.exists() and any(repo.iterdir()):
        raise SystemExit(f"ERROR: target already exists and is not empty: {repo}")
    if worktree.exists() and any(worktree.iterdir()):
        raise SystemExit(f"ERROR: worktree target already exists and is not empty: {worktree}")
    repo.mkdir(parents=True, exist_ok=True)
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.name", "Codex Demo")
    git(repo, "config", "user.email", "codex-demo@example.invalid")
    (repo / "README.md").write_text("# 新能源研发总控台演示仓库\n", encoding="utf-8")
    git(repo, "add", "README.md")
    git(repo, "commit", "-m", "初始化演示主线")
    for branch in ("feat/realtime-dashboard", "fix/chart-render", "codex/integration", "release/v1-rc", "exp/forecast"):
        git(repo, "branch", branch)
    git(repo, "worktree", "add", str(worktree), "feat/realtime-dashboard")
    git(worktree, "config", "user.name", "Codex Demo")
    git(worktree, "config", "user.email", "codex-demo@example.invalid")
    for index in range(9):
        (worktree / "dashboard.txt").write_text(f"dashboard revision {index}\n", encoding="utf-8")
        git(worktree, "add", "dashboard.txt")
        git(worktree, "commit", "-m", f"仪表盘迭代 {index + 1}")
    (worktree / "待处理.txt").write_text("用于演示未跟踪文件提醒\n", encoding="utf-8")
    common = Path(git(repo, "rev-parse", "--git-common-dir"))
    if not common.is_absolute():
        common = (repo / common).resolve()
    status_dir = common / "codex-dashboard"
    status_dir.mkdir(parents=True, exist_ok=True)
    status = {
        "schema_version": 1,
        "project": {"display_name": "新能源中文演示仓库", "canonical_worktree": str(repo), "main_branch": "main", "integration_branch": "codex/integration", "rc_branch": "release/v1-rc"},
        "branches": {
            "feat/realtime-dashboard": {
                "branch_type": "feature", "task_name": "实时经营看板", "objective": "展示状态元数据、提交折叠与脏工作区提醒", "codex_task_id": "DEMO-001", "codex_session_title": "演示任务", "owner": "Codex", "status": "validating", "phase": "integration_test", "result": "PARTIAL", "progress_mode": "weighted", "phase_progress": {"requirement": 100, "design": 100, "development": 90, "unit_test": 80, "integration_test": 60, "acceptance": 20, "merge": 0}, "tests": {"unit": "8/8 PASS", "integration": "RUNNING", "e2e": "NOT_RUN"}, "blockers": [], "next_actions": ["完成端到端验收"], "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    }
    (status_dir / "status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"DEMO_REPO_STATUS=PASS repo={repo} worktree={worktree}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
