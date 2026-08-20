import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  Node,
  NodeMouseHandler,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
} from '@xyflow/react'
import type { GraphData, GraphNodeData } from '../types/domain'
import { BranchNode, CollapsedNode, CommitNode, ProjectNode, TaskNode, branchColors } from './GraphNodes'

const nodeTypes = { project: ProjectNode, branch: BranchNode, commit: CommitNode, collapsed: CollapsedNode, task: TaskNode }

interface Props {
  graph: GraphData
  selectedBranch?: string
  onSelectBranch: (name: string) => void
  onSelectCommit: (data: GraphNodeData) => void
  loading?: boolean
  scope?: 'focus' | 'all'
  onScopeChange?: (scope: 'focus' | 'all') => void
}

function GraphCanvas({ graph, selectedBranch, onSelectBranch, onSelectCommit, loading, scope = 'focus', onScopeChange }: Props) {
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')
  const [orientation, setOrientation] = useState<'horizontal' | 'vertical'>('horizontal')
  const wrapper = useRef<HTMLDivElement>(null)
  const flow = useReactFlow()

  const visibleBranches = useMemo(() => new Set(graph.nodes.filter((node) => {
    if (node.type !== 'branch') return false
    const branch = String(node.data.branch || '')
    return branch.toLowerCase().includes(search.toLowerCase()) &&
      (typeFilter === 'all' || node.data.branch_type === typeFilter) &&
      (statusFilter === 'all' || node.data.status === statusFilter)
  }).map((node) => String(node.data.branch))), [graph.nodes, search, statusFilter, typeFilter])

  const nodes = useMemo(() => graph.nodes.filter((node) => node.type === 'project' || visibleBranches.has(String(node.data.branch))).map((node) => {
    const position = orientation === 'horizontal' ? node.position : { x: node.position.y * 1.7, y: node.position.x * 0.65 }
    return { ...node, position, selected: node.type === 'branch' && node.data.branch === selectedBranch }
  }) as Node[], [graph.nodes, orientation, selectedBranch, visibleBranches])
  const ids = useMemo(() => new Set(nodes.map((node) => node.id)), [nodes])
  const branchTypes = useMemo(() => new Map(graph.nodes.filter((node) => node.type === 'branch').map((node) => [String(node.data.branch), String(node.data.branch_type)])), [graph.nodes])
  const edges = useMemo(() => graph.edges.filter((edge) => ids.has(edge.source) && ids.has(edge.target)).map((edge) => {
    const branch = String(edge.data?.branch || '')
    const selected = branch === selectedBranch
    return { ...edge, style: { stroke: branchColors[branchTypes.get(branch) || 'unknown'], strokeWidth: selected ? 3 : 1.8, opacity: selected ? 1 : .72 } }
  }), [branchTypes, graph.edges, ids, selectedBranch])

  const click: NodeMouseHandler = (_, node) => {
    const data = node.data as GraphNodeData
    if ((node.type === 'branch' || node.type === 'task') && data.branch) onSelectBranch(data.branch)
    if (node.type === 'commit') onSelectCommit(data)
  }
  const toggleFullscreen = async () => {
    if (!document.fullscreenElement) await wrapper.current?.requestFullscreen()
    else await document.exitFullscreen()
  }

  useEffect(() => {
    if (!nodes.length) return
    const frame = window.requestAnimationFrame(() => {
      void flow.fitView({ padding: 0.08, minZoom: 0.72, maxZoom: 1, duration: 0 }).then(() => {
        const viewport = flow.getViewport()
        const minY = Math.min(...nodes.map((node) => node.position.y))
        const renderedTop = minY * viewport.zoom + viewport.y
        if (renderedTop < 14) {
          void flow.setViewport({ ...viewport, y: viewport.y + 14 - renderedTop }, { duration: 0 })
        }
      })
    })
    return () => window.cancelAnimationFrame(frame)
  }, [flow, graph.generated_at, orientation, search, statusFilter, typeFilter])

  return (
    <section className="graph-panel" id="topology" ref={wrapper} data-testid="topology-graph">
      <div className="panel-title-row">
        <div><small>LIVE REPOSITORY MAP</small><h2>动态分支拓扑图</h2></div>
        <div className="graph-summary"><span className="connection-badge"><span />真实 Git 数据</span><b>已显示 {graph.visible_branches ?? 0} / {graph.total_branches ?? 0}</b></div>
      </div>
      <div className="graph-toolbar">
        <input aria-label="搜索分支" placeholder="搜索分支…" value={search} onChange={(event) => setSearch(event.target.value)} />
        <select aria-label="分支类型" value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}>
          <option value="all">全部类型</option><option value="main">主线</option><option value="integration">集成</option><option value="rc">RC</option><option value="feature">功能</option><option value="fix">修复</option><option value="experiment">实验</option>
        </select>
        <select aria-label="分支状态" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
          <option value="all">全部状态</option><option value="active">开发中</option><option value="validating">验证中</option><option value="waiting_merge">待合并</option><option value="blocked">阻塞</option><option value="merged">已合并</option><option value="stale">长期未更新</option>
        </select>
        <div className="toolbar-spacer" />
        <button className={scope === 'focus' ? 'toolbar-active' : ''} onClick={() => onScopeChange?.(scope === 'focus' ? 'all' : 'focus')}>{scope === 'focus' ? '查看全部分支' : '返回焦点分支'}</button>
        <button title="横纵布局切换" onClick={() => setOrientation((value) => value === 'horizontal' ? 'vertical' : 'horizontal')}>{orientation === 'horizontal' ? '⇆ 横向' : '⇅ 纵向'}</button>
        <button onClick={() => flow.fitView({ padding: 0.08, minZoom: 0.62, maxZoom: 1, duration: 300 })}>适配画布</button>
        <button onClick={() => void toggleFullscreen()}>全屏</button>
      </div>
      <div className="graph-legend">
        {Object.entries({ main: '主线', integration: '集成', rc: 'RC', feature: '功能', fix: '修复', experiment: '实验', archive: '已合并' }).map(([type, label]) => <span key={type}><i style={{ background: branchColors[type] }} />{label}</span>)}
      </div>
      <div className="flow-canvas">
        {loading && <div className="graph-loading"><span />正在生成压缩图谱…</div>}
        <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} onNodeClick={click} minZoom={0.35} maxZoom={2} defaultEdgeOptions={{ style: { stroke: '#3b82f6', strokeWidth: 2 } }}>
          <Background variant={BackgroundVariant.Dots} gap={24} size={1} color="#20324a" />
          <Controls position="bottom-left" />
          <MiniMap position="bottom-right" pannable zoomable nodeColor={(node) => branchColors[String(node.data?.branch_type || 'unknown')]} maskColor="rgba(5, 13, 25, .78)" />
        </ReactFlow>
      </div>
    </section>
  )
}

export function BranchTopologyGraph(props: Props) {
  return <ReactFlowProvider><GraphCanvas {...props} /></ReactFlowProvider>
}
