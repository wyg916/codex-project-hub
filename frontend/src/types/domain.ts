export type BranchType = 'main' | 'integration' | 'rc' | 'release' | 'feature' | 'fix' | 'experiment' | 'archive' | 'unknown'
export type BranchStatus = 'active' | 'validating' | 'waiting_merge' | 'blocked' | 'paused' | 'merged' | 'stale' | 'archived' | 'idle' | 'unknown'

export interface Overview {
  active: number
  waiting_merge: number
  blocked: number
  dirty: number
  merged: number
  alerts: number
  next_action: string
  metadata_status: string
}

export interface Project {
  id: number
  name: string
  repo_path: string
  canonical_worktree: string
  remote_url?: string
  git_common_dir: string
  main_branch: string
  integration_branch?: string
  rc_branch?: string
  project_stage: string
  priority: number
  last_scan_at?: string
  scan_status: string
  overview: Overview
}

export interface BranchTask {
  branch_type: BranchType
  task_name: string
  objective: string
  codex_task_id: string
  codex_session_title: string
  owner: string
  status: BranchStatus
  phase: string
  result: 'PASS' | 'PARTIAL' | 'BLOCKED' | 'FAIL' | 'UNKNOWN'
  progress?: number | null
  phase_progress: Record<string, number>
  tests: Record<string, string>
  blockers: string[]
  next_actions: string[]
  updated_at?: string
}

export interface Branch {
  name: string
  branch_type: BranchType
  status: BranchStatus
  head_sha: string
  head_message: string
  head_author: string
  head_time: string
  upstream?: string
  ahead?: number | null
  behind?: number | null
  worktree_path?: string
  is_checked_out: boolean
  is_merged_to_main: boolean
  merge_base_sha?: string
  modified_count: number
  added_count: number
  deleted_count: number
  untracked_count: number
  conflict_count: number
  changed_files?: string[]
  task?: BranchTask | null
  maintenance_status: string
}

export interface Worktree {
  path: string
  path_exists: boolean
  branch?: string | null
  head_sha?: string | null
  is_bare: boolean
  is_locked: boolean
  is_prunable: boolean
  modified_count: number
  added_count: number
  deleted_count: number
  untracked_count: number
  conflict_count: number
  changed_files: string[]
}

export interface GraphNodeData extends Record<string, unknown> {
  label: string
  branch?: string
  branch_type?: BranchType
  status?: BranchStatus
  task_name?: string
  head_sha?: string
  result?: string
  progress?: number | null
  message?: string
  author?: string
  time?: string
  owner?: string
  blockers?: string[]
  is_focus?: boolean
  branch_count?: number
  is_checked_out?: boolean
}

export interface GraphData {
  nodes: Array<{ id: string; type: string; position: { x: number; y: number }; data: GraphNodeData }>
  edges: Array<{ id: string; source: string; target: string; type: string; animated: boolean; data?: { branch?: string } }>
  generated_at: string
  scope?: 'focus' | 'all'
  visible_branches?: number
  total_branches?: number
  focus_limit?: number
}

export interface ProjectEvent {
  id: number
  branch_name?: string
  event_type: string
  severity: string
  title: string
  detail: string
  occurred_at: string
}

export interface Alert {
  alert_type: string
  severity: 'info' | 'attention' | 'blocking'
  message: string
  branch_name?: string
  last_seen_at: string
}
