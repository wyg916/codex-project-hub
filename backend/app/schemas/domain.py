from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator


BranchType = Literal[
    "main", "integration", "rc", "release", "feature", "fix", "experiment", "archive", "unknown"
]
BranchStatus = Literal[
    "active", "validating", "waiting_merge", "blocked", "paused", "merged", "stale", "archived", "idle", "unknown"
]
ResultType = Literal["PASS", "PARTIAL", "BLOCKED", "FAIL", "UNKNOWN"]
PhaseName = Literal[
    "requirement", "design", "development", "unit_test", "integration_test", "acceptance", "merge"
]
ListText = Annotated[str, StringConstraints(max_length=2048)]


class ProjectCreate(BaseModel):
    name: str | None = Field(default=None, max_length=256)
    repo_path: str = Field(min_length=1, max_length=4096)
    canonical_worktree: str | None = Field(default=None, max_length=4096)
    main_branch: str | None = Field(default=None, max_length=1024)
    integration_branch: str | None = Field(default=None, max_length=1024)
    rc_branch: str | None = Field(default=None, max_length=1024)
    project_stage: str = Field(default="未维护", max_length=256)
    priority: int = Field(default=0, ge=-10_000, le=10_000)

    @field_validator("repo_path", "canonical_worktree")
    @classmethod
    def strip_paths(cls, value: str | None) -> str | None:
        return value.strip() if value else value


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=256)
    canonical_worktree: str | None = Field(default=None, max_length=4096)
    main_branch: str | None = Field(default=None, max_length=1024)
    integration_branch: str | None = Field(default=None, max_length=1024)
    rc_branch: str | None = Field(default=None, max_length=1024)
    project_stage: str | None = Field(default=None, max_length=256)
    priority: int | None = Field(default=None, ge=-10_000, le=10_000)


class BranchTask(BaseModel):
    model_config = ConfigDict(extra="allow")

    branch_type: BranchType = "unknown"
    task_name: str = Field(default="", max_length=512)
    objective: str = Field(default="", max_length=4096)
    codex_task_id: str = Field(default="", max_length=256)
    codex_session_title: str = Field(default="", max_length=512)
    owner: str = Field(default="", max_length=256)
    status: BranchStatus = "unknown"
    phase: PhaseName | Literal[""] = ""
    result: ResultType = "UNKNOWN"
    progress_mode: str = Field(default="weighted", max_length=32)
    phase_progress: dict[PhaseName, int] = Field(default_factory=dict, max_length=7)
    tests: dict[str, str] = Field(
        default_factory=lambda: {"unit": "NOT_RUN", "integration": "NOT_RUN", "e2e": "NOT_RUN"},
        max_length=32,
    )
    blockers: list[ListText] = Field(default_factory=list, max_length=100)
    next_actions: list[ListText] = Field(default_factory=list, max_length=100)
    updated_at: datetime | None = None

    @field_validator("phase_progress")
    @classmethod
    def validate_progress(cls, value: dict[str, int]) -> dict[str, int]:
        for progress in value.values():
            if not 0 <= progress <= 100:
                raise ValueError("phase progress must be between 0 and 100")
        return value

    @field_validator("tests")
    @classmethod
    def validate_tests(cls, value: dict[str, str]) -> dict[str, str]:
        if any(len(key) > 128 or len(result) > 256 for key, result in value.items()):
            raise ValueError("test metadata is too long")
        return value


class ProjectMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    display_name: str = Field(max_length=256)
    canonical_worktree: str = Field(max_length=4096)
    main_branch: str = Field(max_length=1024)
    integration_branch: str = Field(default="", max_length=1024)
    rc_branch: str = Field(default="", max_length=1024)


class StatusMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: Literal[1]
    project: ProjectMetadata
    branches: dict[str, BranchTask] = Field(max_length=2000)

    @field_validator("branches")
    @classmethod
    def validate_branch_names(cls, value: dict[str, BranchTask]) -> dict[str, BranchTask]:
        if any(not name or len(name) > 1024 for name in value):
            raise ValueError("branch name is invalid")
        return value


class BranchStatusUpdate(BaseModel):
    branch_name: str = Field(min_length=1, max_length=1024)
    data: BranchTask


class ActionRequest(BaseModel):
    project_id: int = Field(gt=0)
    path: str | None = Field(default=None, max_length=4096)
    branch_name: str | None = Field(default=None, max_length=1024)


def weighted_progress(task: dict[str, Any] | BranchTask | None) -> int | None:
    if task is None:
        return None
    values = task.phase_progress if isinstance(task, BranchTask) else task.get("phase_progress", {})
    if not values:
        return None
    weights = {
        "requirement": 0.10,
        "design": 0.10,
        "development": 0.35,
        "unit_test": 0.15,
        "integration_test": 0.15,
        "acceptance": 0.10,
        "merge": 0.05,
    }
    return round(sum(max(0, min(100, values.get(key, 0))) * weight for key, weight in weights.items()))
