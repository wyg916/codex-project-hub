import { useEffect, useMemo, useState } from 'react'
import { api } from '../api/client'
import { PrimarySidebar } from '../components/PrimarySidebar'
import { ProjectCard } from '../components/ProjectCard'
import { ProjectEditorDialog } from '../components/ProjectEditorDialog'
import type { Project } from '../types/domain'

const filters = ['全部', '开发中', '验证中', '阻塞', '待合并', '已冻结', '长期未更新']

export function OverviewPage() {
  const [projects, setProjects] = useState<Project[]>([])
  const [filter, setFilter] = useState('全部')
  const [editorOpen, setEditorOpen] = useState(false)
  const [editing, setEditing] = useState<Project | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const load = async () => {
    try {
      setProjects(await api.listProjects())
      setError('')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '读取项目失败')
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => { void load() }, [])
  const visible = useMemo(() => projects.filter((project) => {
    if (filter === '全部') return true
    if (filter === '阻塞') return project.overview.blocked > 0
    if (filter === '待合并') return project.overview.waiting_merge > 0
    if (filter === '开发中') return project.overview.active > 0
    if (filter === '验证中') return project.project_stage.includes('验证')
    if (filter === '已冻结') return project.project_stage.includes('冻结')
    if (filter === '长期未更新') return project.project_stage.includes('停滞')
    return true
  }), [filter, projects])
  const save = async (payload: Record<string, unknown>) => {
    if (editing) await api.updateProject(editing.id, payload)
    else await api.createProject(payload)
    await load()
  }
  const remove = async (project: Project) => {
    if (!window.confirm(`仅从总控台删除“${project.name}”？不会修改该 Git 项目。`)) return
    try {
      await api.deleteProject(project.id)
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '删除失败')
    }
  }
  return (
    <div className="app-shell overview-shell">
      <PrimarySidebar />
      <main className="overview-page">
        <header className="overview-header"><div><small>LOCAL MULTI-PROJECT DASHBOARD</small><h1>Codex Project Hub</h1><p>用真实 Git 事实与显式任务元数据，统一掌握分支、Worktree 和研发进度。</p></div><div className="header-actions"><span className="connection-badge"><span />本地安全模式</span><button className="primary-button" onClick={() => { setEditing(null); setEditorOpen(true) }}>＋ 新增项目</button></div></header>
        <section className="overview-stats">
          <div><small>登记项目</small><strong>{projects.length}</strong></div><div><small>活跃分支</small><strong>{projects.reduce((sum, project) => sum + project.overview.active, 0)}</strong></div><div><small>待合并</small><strong>{projects.reduce((sum, project) => sum + project.overview.waiting_merge, 0)}</strong></div><div><small>异常提醒</small><strong className="warning-text">{projects.reduce((sum, project) => sum + project.overview.alerts, 0)}</strong></div>
        </section>
        <div className="overview-toolbar"><div className="filter-tabs">{filters.map((value) => <button className={filter === value ? 'active' : ''} key={value} onClick={() => setFilter(value)}>{value}</button>)}</div><button onClick={() => void load()}>↻ 刷新全部</button></div>
        {error && <div className="page-error" role="alert">{error}</div>}
        {loading ? <div className="empty-state">正在读取本地项目配置…</div> : visible.length ? <div className="project-grid">{visible.map((project) => <ProjectCard key={project.id} project={project} onEdit={(value) => { setEditing(value); setEditorOpen(true) }} onDelete={(value) => void remove(value)} />)}</div> : <div className="empty-state" data-testid="empty-projects"><div className="empty-orbit">C</div><h2>{projects.length ? '当前筛选下没有项目' : '还没有登记项目'}</h2><p>登记一个本地 Git 仓库后，总控台会使用只读命令扫描真实分支和 Worktree。</p><button className="primary-button" onClick={() => { setEditing(null); setEditorOpen(true) }}>登记第一个项目</button></div>}
      </main>
      <ProjectEditorDialog open={editorOpen} project={editing} onClose={() => setEditorOpen(false)} onSave={save} />
    </div>
  )
}
