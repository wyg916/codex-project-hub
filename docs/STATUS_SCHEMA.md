# Codex Project Hub 分支状态 Schema v1

文件位置：`<git-common-dir>/codex-dashboard/status.json`。编码为 UTF-8，`schema_version` 当前必须为 `1`。

## JSON Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "urn:codex-project-hub:status-schema:v1",
  "title": "Codex Project Hub Status",
  "type": "object",
  "required": ["schema_version", "project", "branches"],
  "properties": {
    "schema_version": { "const": 1 },
    "project": {
      "type": "object",
      "required": ["display_name", "canonical_worktree", "main_branch"],
      "properties": {
        "display_name": { "type": "string", "maxLength": 256 },
        "canonical_worktree": { "type": "string", "maxLength": 4096 },
        "main_branch": { "type": "string", "maxLength": 1024 },
        "integration_branch": { "type": "string", "maxLength": 1024 },
        "rc_branch": { "type": "string", "maxLength": 1024 }
      },
      "additionalProperties": true
    },
    "branches": {
      "type": "object",
      "maxProperties": 2000,
      "propertyNames": { "minLength": 1, "maxLength": 1024 },
      "additionalProperties": { "$ref": "#/$defs/branchTask" }
    }
  },
  "$defs": {
    "branchTask": {
      "type": "object",
      "properties": {
        "branch_type": { "enum": ["main", "integration", "rc", "release", "feature", "fix", "experiment", "archive", "unknown"] },
        "task_name": { "type": "string", "maxLength": 512 },
        "objective": { "type": "string", "maxLength": 4096 },
        "codex_task_id": { "type": "string", "maxLength": 256 },
        "codex_session_title": { "type": "string", "maxLength": 512 },
        "owner": { "type": "string", "maxLength": 256 },
        "status": { "enum": ["active", "validating", "waiting_merge", "blocked", "paused", "merged", "stale", "archived", "idle", "unknown"] },
        "phase": { "enum": ["", "requirement", "design", "development", "unit_test", "integration_test", "acceptance", "merge"] },
        "result": { "enum": ["PASS", "PARTIAL", "BLOCKED", "FAIL", "UNKNOWN"] },
        "progress_mode": { "type": "string", "maxLength": 32 },
        "phase_progress": {
          "type": "object",
          "maxProperties": 7,
          "properties": {
            "requirement": { "$ref": "#/$defs/progress" },
            "design": { "$ref": "#/$defs/progress" },
            "development": { "$ref": "#/$defs/progress" },
            "unit_test": { "$ref": "#/$defs/progress" },
            "integration_test": { "$ref": "#/$defs/progress" },
            "acceptance": { "$ref": "#/$defs/progress" },
            "merge": { "$ref": "#/$defs/progress" }
          },
          "additionalProperties": false
        },
        "tests": {
          "type": "object",
          "maxProperties": 32,
          "propertyNames": { "maxLength": 128 },
          "properties": {
            "unit": { "type": "string", "maxLength": 256 },
            "integration": { "type": "string", "maxLength": 256 },
            "e2e": { "type": "string", "maxLength": 256 }
          },
          "additionalProperties": { "type": "string", "maxLength": 256 }
        },
        "blockers": { "type": "array", "maxItems": 100, "items": { "type": "string", "maxLength": 2048 } },
        "next_actions": { "type": "array", "maxItems": 100, "items": { "type": "string", "maxLength": 2048 } },
        "updated_at": { "type": ["string", "null"], "format": "date-time" }
      },
      "additionalProperties": true
    },
    "progress": { "type": "integer", "minimum": 0, "maximum": 100 }
  },
  "additionalProperties": true
}
```

## 权重

总进度只在存在 `phase_progress` 时计算：需求 10%、设计 10%、开发 35%、单元测试 15%、集成测试 15%、验收 10%、合并 5%。提交数量不参与进度计算。

## 写入保证

后端和 CLI 均先校验，再通过同目录临时文件、flush/fsync 与 `os.replace` 原子更新。每次显式写入使用 `status.lock` 进行跨进程协调；等待写锁超过 5 秒会失败。覆盖已有有效状态前会生成带 UTC 时间的 `.bak.json`，并最多保留 5 份备份。编码后的 `status.json` 上限为 1 MiB；损坏、超限或路径不安全的文件会被拒绝，不会被静默覆盖。
