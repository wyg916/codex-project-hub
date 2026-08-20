import type { Branch, GraphData, Project, Worktree } from '../src/types/domain'

export const project: Project = {
  id: 1,
  name: 'Project Alpha',
  repo_path: 'example-workspace/project-alpha',
  canonical_worktree: 'example-workspace/project-alpha',
  git_common_dir: 'example-workspace/project-alpha/.git',
  main_branch: 'main',
  integration_branch: 'feat/dashboard',
  rc_branch: 'release/rc',
  project_stage: 'Demo',
  priority: 1,
  scan_status: 'ok',
  last_scan_at: '2026-08-16T10:00:00Z',
  overview: { active: 2, waiting_merge: 1, blocked: 0, dirty: 1, merged: 0, alerts: 1, next_action: 'Review demo results', metadata_status: 'Demo metadata' },
}

export const branch: Branch = {
  name: 'feat/dashboard', branch_type: 'feature', status: 'active', head_sha: '1234567890abcdef', head_message: 'Example feature commit', head_author: 'Example Developer', head_time: '2026-08-16T10:00:00Z', upstream: 'origin/feat/dashboard', ahead: 1, behind: 0, worktree_path: 'example-workspace/project-alpha-worktree', is_checked_out: true, is_merged_to_main: false, merge_base_sha: 'abcdef1234', modified_count: 1, added_count: 0, deleted_count: 0, untracked_count: 1, conflict_count: 0, changed_files: ['src/example-dashboard.tsx', 'notes/demo.txt'], maintenance_status: 'Demo metadata', task: null,
}

export const worktree: Worktree = {
  path: 'example-workspace/project-alpha-worktree',
  path_exists: true,
  branch: 'feat/dashboard',
  head_sha: '1234567890abcdef',
  is_bare: false,
  is_locked: false,
  is_prunable: false,
  modified_count: 1,
  added_count: 0,
  deleted_count: 0,
  untracked_count: 1,
  conflict_count: 0,
  changed_files: ['src/example-dashboard.tsx', 'notes/demo.txt'],
}

export const graph: GraphData = {
  generated_at: '2026-08-16T10:00:00Z',
  nodes: [
    { id: 'project:root', type: 'project', position: { x: 0, y: 0 }, data: { label: 'Project Alpha' } },
    { id: 'branch:main', type: 'branch', position: { x: 250, y: 0 }, data: { label: 'main', branch: 'main', branch_type: 'main', status: 'active', task_name: 'Example mainline', head_sha: 'aaaa' } },
    { id: 'branch:feat/dashboard', type: 'branch', position: { x: 250, y: 150 }, data: { label: 'feat/dashboard', branch: 'feat/dashboard', branch_type: 'feature', status: 'active', task_name: 'Example Dashboard Task', head_sha: 'bbbb' } },
  ],
  edges: [
    { id: 'e1', source: 'project:root', target: 'branch:main', type: 'smoothstep', animated: true },
    { id: 'e2', source: 'project:root', target: 'branch:feat/dashboard', type: 'smoothstep', animated: true },
  ],
}
