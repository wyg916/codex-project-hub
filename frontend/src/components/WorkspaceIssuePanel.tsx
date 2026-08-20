import type { Worktree } from '../types/domain'
import { compactLocalPath } from '../utils/paths'

interface Props {
  worktrees: Worktree[]
  onSelectBranch: (name: string) => void
}

const dirtyCount = (worktree: Worktree) => worktree.modified_count + worktree.added_count + worktree.deleted_count + worktree.untracked_count + worktree.conflict_count

export function WorkspaceIssuePanel({ worktrees, onSelectBranch }: Props) {
  const totalChanges = worktrees.reduce((total, worktree) => total + dirtyCount(worktree), 0)
  return (
    <aside className="detail-panel workspace-issues" data-testid="dirty-worktree-detail">
      <div className="detail-title"><span />脏工作区详情</div>
      <section className="workspace-issue-summary">
        <div><strong>{worktrees.length}</strong><span>个异常工作区</span></div>
        <div><strong>{totalChanges}</strong><span>项待处理变更</span></div>
      </section>
      <section>
        <h4>按工作区查看</h4>
        <div className="workspace-issue-list">
          {worktrees.map((worktree) => {
            const branchName = worktree.branch && worktree.branch !== 'DETACHED' ? worktree.branch : null
            const label = branchName || 'DETACHED HEAD'
            return (
            <button type="button" key={worktree.path} onClick={() => branchName && onSelectBranch(branchName)} aria-label={`查看 ${label} 工作区详情`}>
              <div className="workspace-issue-head"><strong>{label}</strong><b>{dirtyCount(worktree)} 项</b></div>
              <small title={worktree.path}>{compactLocalPath(worktree.path, '未检出 Worktree')}</small>
              <div className="change-counts">
                {!!worktree.modified_count && <span>修改 {worktree.modified_count}</span>}
                {!!worktree.added_count && <span>新增 {worktree.added_count}</span>}
                {!!worktree.deleted_count && <span>删除 {worktree.deleted_count}</span>}
                {!!worktree.untracked_count && <span>未跟踪 {worktree.untracked_count}</span>}
                {!!worktree.conflict_count && <span className="danger-text">冲突 {worktree.conflict_count}</span>}
              </div>
              <em>{branchName ? '查看 Git 事实与文件明细 →' : '脱离 HEAD 工作区，请在本地处理'}</em>
            </button>
          )})}
        </div>
      </section>
    </aside>
  )
}
