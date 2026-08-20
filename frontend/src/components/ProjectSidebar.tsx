import { Link } from 'react-router-dom'
import type { Alert, Branch, Project, ProjectEvent } from '../types/domain'
import { branchStatusLabels } from './GraphNodes'

interface Props {
  projects: Project[]
  selectedId: number
  events: ProjectEvent[]
  alerts: Alert[]
  branches?: Branch[]
  selectedAlertKey?: string
  onSelectAlert?: (alert: Alert) => void
}

export const getAlertKey = (alert: Alert) => `${alert.alert_type}:${alert.branch_name || 'project'}:${alert.message}`

export function ProjectSidebar({ projects, selectedId, events, alerts, branches = [], selectedAlertKey, onSelectAlert }: Props) {
  const statusOf = (branch: Branch) => branch.task?.status || branch.status
  const counts = {
    active: branches.filter((branch) => ['active', 'validating'].includes(statusOf(branch))).length,
    waiting: branches.filter((branch) => statusOf(branch) === 'waiting_merge').length,
    blocked: branches.filter((branch) => statusOf(branch) === 'blocked').length,
    merged: branches.filter((branch) => ['merged', 'archived'].includes(statusOf(branch))).length,
  }
  const total = Math.max(branches.length, 1)
  const activeEnd = counts.active / total * 100
  const waitingEnd = activeEnd + counts.waiting / total * 100
  const blockedEnd = waitingEnd + counts.blocked / total * 100
  const mergedEnd = blockedEnd + counts.merged / total * 100
  const visibleAlerts = [...alerts].sort((left, right) => {
    const priority = (alert: Alert) => alert.severity === 'blocking' ? 0 : alert.alert_type === 'dirty_worktree' ? 1 : 2
    return priority(left) - priority(right)
  }).slice(0, 6)
  return (
    <aside className="project-sidebar">
      <section><div className="section-label">项目列表 <span>{projects.length}</span></div><div className="compact-project-list">{projects.map((project) => <Link className={project.id === selectedId ? 'selected' : ''} to={`/projects/${project.id}`} key={project.id}><span className="health-dot online" /><div><strong>{project.name}</strong><small>{project.overview.active} 活跃 / {project.overview.alerts} 提醒</small></div></Link>)}</div></section>
      <section className="status-overview"><div className="section-label">项目状态概览 <span>{branches.length} 分支</span></div><div className="status-overview-body"><div className="status-donut" style={{ background: `conic-gradient(#3b82f6 0 ${activeEnd}%, #fbbf24 ${activeEnd}% ${waitingEnd}%, #ef4444 ${waitingEnd}% ${blockedEnd}%, #64748b ${blockedEnd}% ${mergedEnd}%, #17304d ${mergedEnd}% 100%)` }}><div><strong>{branches.length}</strong><small>总分支</small></div></div><div className="status-legend"><span><i className="blue" />{branchStatusLabels.active}<b>{counts.active}</b></span><span><i className="yellow" />{branchStatusLabels.waiting_merge}<b>{counts.waiting}</b></span><span><i className="red" />{branchStatusLabels.blocked}<b>{counts.blocked}</b></span><span><i className="gray" />{branchStatusLabels.merged}<b>{counts.merged}</b></span></div></div></section>
      <section id="alerts"><div className="section-label">异常提醒 <span>{alerts.length}</span></div><div className="mini-feed alert-feed">{visibleAlerts.length ? visibleAlerts.map((alert) => <button type="button" key={getAlertKey(alert)} className={`${alert.severity} ${selectedAlertKey === getAlertKey(alert) ? 'selected' : ''}`} onClick={() => onSelectAlert?.(alert)} aria-label={`查看异常详情：${alert.message}`}><i /><span><b>{alert.alert_type === 'dirty_worktree' ? '脏工作区' : alert.severity === 'blocking' ? '阻塞异常' : '异常提醒'}</b><p>{alert.message}</p><em>查看详情 →</em></span></button>) : <p className="empty-copy">暂无异常</p>}</div>{alerts.length > visibleAlerts.length && <small className="feed-hint">优先显示阻塞与脏工作区，共 {alerts.length} 条</small>}</section>
      <section><div className="section-label">最近活动 <span>{events.length}</span></div><div className="mini-feed timeline">{events.length ? events.slice(0, 8).map((event) => <div key={event.id}><time>{new Date(event.occurred_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}</time><p><strong>{event.branch_name}</strong>{event.title}</p></div>) : <p className="empty-copy">等待 Git 变化</p>}</div></section>
    </aside>
  )
}
