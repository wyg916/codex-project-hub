import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { BranchDetailPanel } from '../components/BranchDetailPanel'
import { BranchTopologyGraph } from '../components/BranchTopologyGraph'
import { PrimarySidebar } from '../components/PrimarySidebar'
import { ProjectSidebar, getAlertKey } from '../components/ProjectSidebar'
import { WorkspaceIssuePanel } from '../components/WorkspaceIssuePanel'
import type { Alert, Branch, GraphData, GraphNodeData, Project, ProjectEvent, Worktree } from '../types/domain'
import { compactLocalPath } from '../utils/paths'

const emptyGraph: GraphData = { nodes: [], edges: [], generated_at: '', scope: 'focus', visible_branches: 0, total_branches: 0 }

export function ProjectDashboard() {
  const id = Number(useParams().projectId)
  const navigate = useNavigate()
  const [project, setProject] = useState<Project | null>(null)
  const [projects, setProjects] = useState<Project[]>([])
  const [branches, setBranches] = useState<Branch[]>([])
  const [worktrees, setWorktrees] = useState<Worktree[]>([])
  const [graph, setGraph] = useState<GraphData>(emptyGraph)
  const [graphScope, setGraphScope] = useState<'focus' | 'all'>('focus')
  const [graphLoading, setGraphLoading] = useState(true)
  const [events, setEvents] = useState<ProjectEvent[]>([])
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [selectedBranch, setSelectedBranch] = useState('')
  const [selectedCommit, setSelectedCommit] = useState<GraphNodeData | null>(null)
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null)
  const [detailView, setDetailView] = useState<'branch' | 'commit' | 'alert' | 'dirty'>('branch')
  const [connection, setConnection] = useState<'connecting' | 'online' | 'offline'>('connecting')
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')
  const reconnectTimer = useRef<number>()
  const realtimeTimer = useRef<number>()
  const shellVersion = useRef(0)
  const graphVersion = useRef(0)
  const scopeRef = useRef<'focus' | 'all'>('focus')

  const loadShell = useCallback(async () => {
    if (!Number.isInteger(id)) return
    const version = ++shellVersion.current
    try {
      const current = await api.getProject(id)
      if (version !== shellVersion.current) return
      setProject(current)
      setSelectedBranch((value) => value || current.main_branch)
      const [all, nextBranches, nextWorktrees] = await Promise.all([
        api.listProjects(),
        api.branches(id),
        api.worktrees(id),
      ])
      if (version !== shellVersion.current) return
      setProjects(all)
      setBranches(nextBranches)
      setWorktrees(nextWorktrees)
      setSelectedBranch((value) => nextBranches.some((branch) => branch.name === value) ? value : current.main_branch)
      setError('')
    } catch (reason) {
      if (version === shellVersion.current) setError(reason instanceof Error ? reason.message : '项目加载失败')
    }
  }, [id])

  const loadActivity = useCallback(async () => {
    if (!Number.isInteger(id)) return
    try {
      const [nextEvents, nextAlerts] = await Promise.all([api.events(id), api.alerts(id)])
      setEvents(nextEvents)
      setAlerts(nextAlerts)
    } catch {
      // Activity is secondary; the visible shell keeps the last trusted data.
    }
  }, [id])

  const loadGraph = useCallback(async (scope: 'focus' | 'all') => {
    if (!Number.isInteger(id)) return
    const version = ++graphVersion.current
    setGraphLoading(true)
    try {
      const nextGraph = await api.graph(id, scope)
      if (version === graphVersion.current) setGraph(nextGraph)
    } catch (reason) {
      if (version === graphVersion.current) setError(reason instanceof Error ? reason.message : '图谱加载失败')
    } finally {
      if (version === graphVersion.current) setGraphLoading(false)
    }
  }, [id])

  const reloadRealtime = useCallback(() => {
    window.clearTimeout(realtimeTimer.current)
    realtimeTimer.current = window.setTimeout(() => {
      void Promise.all([loadShell(), loadActivity(), loadGraph(scopeRef.current)])
    }, 180)
  }, [loadActivity, loadGraph, loadShell])

  useEffect(() => {
    scopeRef.current = 'focus'
    setGraphScope('focus')
    setGraph(emptyGraph)
    setProject(null)
    setBranches([])
    setWorktrees([])
    setSelectedBranch('')
    setSelectedCommit(null)
    setSelectedAlert(null)
    setDetailView('branch')
    void loadShell()
    void loadActivity()
    void loadGraph('focus')
    return () => window.clearTimeout(realtimeTimer.current)
  }, [id, loadActivity, loadGraph, loadShell])

  useEffect(() => {
    const interval = connection === 'online' ? 20_000 : 4_000
    const fallback = window.setInterval(() => {
      void loadShell()
      void loadActivity()
      if (connection !== 'online') void loadGraph(scopeRef.current)
    }, interval)
    return () => window.clearInterval(fallback)
  }, [connection, loadActivity, loadGraph, loadShell])

  useEffect(() => {
    let active = true
    let socket: WebSocket | null = null
    let heartbeat = 0
    let attempts = 0
    const connect = () => {
      if (!active) return
      setConnection('connecting')
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      socket = new WebSocket(`${protocol}//${window.location.host}/ws/projects/${id}`)
      socket.onopen = () => {
        attempts = 0
        setConnection('online')
        heartbeat = window.setInterval(() => {
          if (socket?.readyState === WebSocket.OPEN) socket.send('ping')
        }, 20_000)
      }
      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data) as { type?: string }
          if (message.type === 'pong' || message.type === 'connected') {
            setConnection('online')
          } else if (message.type === 'snapshot.updated' || message.type === 'branch.updated') {
            reloadRealtime()
          } else if (message.type?.startsWith('event.') || message.type?.startsWith('alert.')) {
            void loadActivity()
          }
        } catch {
          setConnection('offline')
        }
      }
      socket.onerror = () => setConnection('offline')
      socket.onclose = () => {
        window.clearInterval(heartbeat)
        setConnection('offline')
        if (active) {
          const delay = Math.min(15_000, 1_000 * 2 ** attempts++)
          reconnectTimer.current = window.setTimeout(connect, delay)
        }
      }
    }
    connect()
    return () => {
      active = false
      window.clearInterval(heartbeat)
      window.clearTimeout(reconnectTimer.current)
      socket?.close()
    }
  }, [id, loadActivity, reloadRealtime])

  const selected = useMemo(() => branches.find((branch) => branch.name === selectedBranch), [branches, selectedBranch])
  const dirtyBranches = useMemo(() => branches.filter((branch) => branch.modified_count + branch.added_count + branch.deleted_count + branch.untracked_count + branch.conflict_count > 0), [branches])
  const dirtyWorktrees = useMemo(() => worktrees.filter((worktree) => worktree.modified_count + worktree.added_count + worktree.deleted_count + worktree.untracked_count + worktree.conflict_count > 0), [worktrees])
  const activeAlert = useMemo(() => selectedAlert ? alerts.find((alert) => getAlertKey(alert) === getAlertKey(selectedAlert)) || selectedAlert : null, [alerts, selectedAlert])
  if (!project) return (
    <div className="app-shell dashboard-shell"><PrimarySidebar /><div className="dashboard-area"><header className="top-header"><Link to="/" className="wordmark">Codex <strong>Project Hub</strong></Link></header><main className="dashboard-skeleton"><span />{error || '正在读取项目快照…'}<small>界面骨架与压缩图谱将分阶段加载</small></main></div></div>
  )
  const dirty = dirtyWorktrees.length
  const current = branches.find((branch) => branch.name === project.main_branch)
  const refresh = async () => {
    setRefreshing(true)
    try {
      await api.refreshProject(id)
      await Promise.all([loadShell(), loadActivity(), loadGraph(scopeRef.current)])
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '刷新失败')
    } finally {
      setRefreshing(false)
    }
  }
  const changeScope = (scope: 'focus' | 'all') => {
    scopeRef.current = scope
    setGraphScope(scope)
    void loadGraph(scope)
  }
  return (
    <div className="app-shell dashboard-shell">
      <PrimarySidebar />
      <div className="dashboard-area">
        <header className="top-header">
          <Link to="/" className="wordmark">Codex <strong>Project Hub</strong></Link>
          <div className="current-project"><small>当前项目</small><select aria-label="切换当前项目" value={project.id} onChange={(event) => navigate(`/projects/${event.target.value}`)}>{projects.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select><span className={`connection-badge ${connection}`}><i />{connection === 'online' ? '实时监控中' : connection === 'connecting' ? '正在连接' : '轮询兜底'}</span></div>
          <div className="top-meta"><span>最后扫描 <b>{project.last_scan_at ? new Date(project.last_scan_at).toLocaleTimeString('zh-CN') : 'UNKNOWN'}</b></span><button className={refreshing ? 'is-spinning' : ''} onClick={() => void refresh()} disabled={refreshing} title="立即刷新">↻</button></div>
        </header>
        {error && <div className="dashboard-error" role="alert">{error}</div>}
        <div className="dashboard-grid">
          <ProjectSidebar projects={projects} selectedId={project.id} events={events} alerts={alerts} branches={branches} selectedAlertKey={detailView === 'alert' && activeAlert ? getAlertKey(activeAlert) : undefined} onSelectAlert={(alert) => { setSelectedAlert(alert); setSelectedBranch(alert.branch_name || ''); setSelectedCommit(null); setDetailView('alert') }} />
          <main className="dashboard-main">
            <section className="summary-header">
              <div className="project-heading"><small>PROJECT COCKPIT</small><h1>{project.name}</h1><p title={project.canonical_worktree}>{compactLocalPath(project.canonical_worktree)}</p></div>
              <div className="summary-facts"><span><small>主分支</small><strong>{project.main_branch}</strong></span><span><small>集成分支</small><strong>{project.integration_branch || '未设置'}</strong></span><span><small>RC 分支</small><strong>{project.rc_branch || '未设置'}</strong></span><span><small>当前 HEAD</small><strong>{current?.head_sha.slice(0, 8) || 'UNKNOWN'}</strong></span><span><small>工作区</small>{dirty ? <button type="button" className="summary-detail-button warning-text" data-testid="dirty-summary" onClick={() => { setSelectedAlert(null); setSelectedCommit(null); setDetailView('dirty') }}>{dirty} 异常 · 查看</button> : <strong className="success-text">Clean</strong>}</span><span><small>远端同步</small><strong className="sync-fact"><span>↑{current?.ahead ?? 'UNKNOWN'}</span><span>↓{current?.behind ?? 'UNKNOWN'}</span></strong></span></div>
            </section>
            <BranchTopologyGraph graph={graph} loading={graphLoading} scope={graphScope} onScopeChange={changeScope} selectedBranch={selectedBranch} onSelectBranch={(name) => { setSelectedBranch(name); setSelectedCommit(null); setSelectedAlert(null); setDetailView('branch') }} onSelectCommit={(data) => { setSelectedBranch(''); setSelectedCommit(data); setSelectedAlert(null); setDetailView('commit') }} />
          </main>
          {detailView === 'dirty' ? <WorkspaceIssuePanel worktrees={dirtyWorktrees} onSelectBranch={(name) => { setSelectedBranch(name); setDetailView('branch') }} /> : <BranchDetailPanel project={project} branch={selected} commit={detailView === 'commit' ? selectedCommit : null} alert={detailView === 'alert' ? activeAlert : null} />}
        </div>
      </div>
    </div>
  )
}
