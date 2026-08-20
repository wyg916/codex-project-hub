import { useState } from 'react'
import { api } from '../api/client'
import type { Alert, Branch, GraphNodeData, Project } from '../types/domain'
import { compactLocalPath } from '../utils/paths'
import { branchStatusLabels, branchTypeLabels } from './GraphNodes'

const phaseLabels: Record<string, string> = {
  requirement: '需求确认', design: '技术设计', development: '核心开发', unit_test: '单元测试', integration_test: '集成测试', acceptance: '验收', merge: '合并收口',
}

interface Props {
  project: Project
  branch?: Branch
  commit?: GraphNodeData | null
  alert?: Alert | null
}

const alertTypeLabels: Record<string, string> = {
  dirty_worktree: '脏工作区', git_conflict: 'Git 冲突', stale_branch: '长期未提交', behind_upstream: '落后上游', test_result: '测试结论异常', pass_git_mismatch: '状态与 Git 不一致', metadata_invalid: '状态元数据异常', worktree_missing: 'Worktree 路径失效', canonical_missing: '主项目目录失效', multiple_rc: '多个 RC 标记', cross_worktree_file: '跨 Worktree 文件冲突', metadata_stale: '状态元数据过期', merged_still_active: '合并状态异常',
}

export function BranchDetailPanel({ project, branch, commit, alert }: Props) {
  const [feedback, setFeedback] = useState('')
  if (commit && !branch) {
    return <aside className="detail-panel"><div className="detail-title"><span />提交详情</div><section><h3>{commit.message || '提交'}</h3><dl><dt>SHA</dt><dd><code>{String(commit.sha || 'UNKNOWN')}</code></dd><dt>作者</dt><dd>{commit.author || 'UNKNOWN'}</dd><dt>时间</dt><dd>{commit.time || 'UNKNOWN'}</dd><dt>分支</dt><dd>{commit.branch || 'UNKNOWN'}</dd></dl></section></aside>
  }
  if (alert && !branch) {
    return <aside className="detail-panel" data-testid="alert-detail"><div className="detail-title danger-title"><span />异常详情</div><section className={`issue-focus ${alert.severity}`}><small>{alertTypeLabels[alert.alert_type] || alert.alert_type}</small><h3>{alert.message}</h3><p>该异常作用于整个项目或多个 Worktree，暂无唯一对应分支。</p></section><section><h4>定位信息</h4><dl><dt>项目</dt><dd>{project.name}</dd><dt>范围</dt><dd>项目级 / 多工作区</dd><dt>严重度</dt><dd>{alert.severity === 'blocking' ? '阻塞' : alert.severity === 'attention' ? '需关注' : '信息'}</dd><dt>最近发现</dt><dd>{new Date(alert.last_seen_at).toLocaleString('zh-CN')}</dd><dt>项目目录</dt><dd title={project.canonical_worktree}>{compactLocalPath(project.canonical_worktree)}</dd></dl></section></aside>
  }
  if (!branch) return <aside className="detail-panel empty-detail"><div className="detail-title"><span />分支详情</div><p>点击拓扑中的分支节点查看真实 Git 状态与任务元数据。</p></aside>
  const task = branch.task
  const dirty = branch.modified_count + branch.added_count + branch.deleted_count + branch.untracked_count + branch.conflict_count
  const status = task?.status || branch.status
  const branchType = task?.branch_type || branch.branch_type
  const perform = async (name: string, path?: string) => {
    try {
      await api.action(name, { project_id: project.id, path: path || branch.worktree_path || project.canonical_worktree })
      setFeedback('操作已提交')
    } catch (reason) {
      setFeedback(reason instanceof Error ? reason.message : '操作失败')
    }
  }
  const copy = async () => {
    try {
      const result = await api.action('copy-summary', { project_id: project.id, branch_name: branch.name })
      await navigator.clipboard.writeText(String(result.summary))
      setFeedback('状态摘要已复制')
    } catch (reason) {
      setFeedback(reason instanceof Error ? reason.message : '复制失败')
    }
  }
  return (
    <aside className="detail-panel" data-testid="branch-detail">
      <div className="detail-title"><span />分支详情</div>
      <section className="branch-identity">
        <h3>⑂ {branch.name}</h3>
        <div className="status-row"><span className={`status-chip ${status}`}>{branchStatusLabels[status] || status}</span><span className="type-chip">{branchTypeLabels[branchType] || branchType}</span><span className="maintenance-chip">{task ? '已维护' : '未维护'}</span></div>
      </section>
      {alert && <section className={`issue-focus ${alert.severity}`} data-testid="alert-detail"><small>{alertTypeLabels[alert.alert_type] || alert.alert_type}</small><h4>{alert.message}</h4><p>最近发现：{new Date(alert.last_seen_at).toLocaleString('zh-CN')}</p></section>}
      <section>
        <h4>基本信息</h4>
        <dl><dt>任务</dt><dd>{task?.task_name || '未维护'}</dd><dt>目标</dt><dd>{task?.objective || '未维护'}</dd><dt>负责人</dt><dd>{task?.owner || '未维护'}</dd><dt>任务标识</dt><dd>{task?.codex_task_id || '未维护'}</dd><dt>Worktree</dt><dd title={branch.worktree_path}>{compactLocalPath(branch.worktree_path)}</dd><dt>状态更新</dt><dd>{task?.updated_at ? new Date(task.updated_at).toLocaleString('zh-CN') : '未维护'}</dd></dl>
      </section>
      <section id="tests">
        <h4>进度信息 <strong>{typeof task?.progress === 'number' ? `${task.progress}%` : '未维护'}</strong></h4>
        <div className="overall-progress"><i style={{ width: `${task?.progress || 0}%` }} /></div>
        <div className="phase-list">
          {Object.entries(phaseLabels).map(([key, label]) => <div key={key}><span>{label}</span><div><i style={{ width: `${task?.phase_progress?.[key] || 0}%` }} /></div><b>{task?.phase_progress?.[key] ?? '—'}{task?.phase_progress?.[key] !== undefined ? '%' : ''}</b></div>)}
        </div>
      </section>
      <section>
        <h4>Git 工程事实</h4>
        <dl><dt>HEAD</dt><dd><code>{branch.head_sha.slice(0, 10)}</code></dd><dt>最新提交</dt><dd>{branch.head_message}</dd><dt>上游</dt><dd>{branch.upstream || 'UNKNOWN'}</dd><dt>同步</dt><dd>ahead {branch.ahead ?? 'UNKNOWN'} / behind {branch.behind ?? 'UNKNOWN'}</dd><dt>工作区</dt><dd className={dirty ? 'warning-text' : 'success-text'}>{dirty ? `Modified (${dirty})` : 'Clean'}</dd><dt>冲突</dt><dd className={branch.conflict_count ? 'danger-text' : ''}>{branch.conflict_count}</dd><dt>已合并</dt><dd>{branch.is_merged_to_main ? '是' : '否'}</dd><dt>merge-base</dt><dd><code>{branch.merge_base_sha?.slice(0, 10) || 'UNKNOWN'}</code></dd></dl>
        {!!dirty && <div className="dirty-breakdown" data-testid="dirty-breakdown"><span>修改 <b>{branch.modified_count}</b></span><span>新增 <b>{branch.added_count}</b></span><span>删除 <b>{branch.deleted_count}</b></span><span>未跟踪 <b>{branch.untracked_count}</b></span><span className={branch.conflict_count ? 'danger-text' : ''}>冲突 <b>{branch.conflict_count}</b></span></div>}
        {!!branch.changed_files?.length && <div className="changed-files"><h5>变更文件（{branch.changed_files.length}）</h5><ul>{branch.changed_files.map((file) => <li key={file}><code>{file}</code></li>)}</ul></div>}
      </section>
      <section>
        <h4>测试与结论 <strong className={`result-${task?.result || 'UNKNOWN'}`}>{task?.result || 'UNKNOWN'}</strong></h4>
        <div className="test-list"><span>Unit <b>{task?.tests?.unit || 'NOT_RUN'}</b></span><span>Integration <b>{task?.tests?.integration || 'NOT_RUN'}</b></span><span>E2E <b>{task?.tests?.e2e || 'NOT_RUN'}</b></span></div>
        <div className="next-card"><small>下一步唯一动作</small><strong>{task?.next_actions?.[0] || '未维护'}</strong></div>
        {!!task?.blockers?.length && <div className="blocker-card">阻塞：{task.blockers.join('；')}</div>}
      </section>
      <section className="quick-actions"><h4>快捷操作</h4><div><button onClick={() => void perform('open-folder')}>打开目录</button><button onClick={() => void perform('open-terminal')}>终端</button><button onClick={() => void perform('open-vscode')}>VS Code</button><button onClick={() => void copy()}>复制摘要</button></div>{feedback && <small>{feedback}</small>}</section>
    </aside>
  )
}
