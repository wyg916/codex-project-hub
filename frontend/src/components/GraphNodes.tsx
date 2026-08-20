import { Handle, NodeProps, Position } from '@xyflow/react'
import type { GraphNodeData } from '../types/domain'

export const branchColors: Record<string, string> = {
  main: '#3b82f6', integration: '#8b5cf6', rc: '#22d3ee', release: '#22d3ee', feature: '#22c55e', fix: '#f97316', experiment: '#ec4899', archive: '#64748b', unknown: '#94a3b8',
}

export const branchTypeLabels: Record<string, string> = {
  main: '主线', integration: '集成', rc: 'RC', release: '发布', feature: '功能', fix: '修复', experiment: '实验', archive: '归档', unknown: '未识别',
}

export const branchStatusLabels: Record<string, string> = {
  active: '开发中', validating: '验证中', waiting_merge: '待合并', blocked: '阻塞', paused: '暂停', merged: '已合并', stale: '长期未更新', archived: '已归档', idle: '暂无活动', unknown: '未知',
}

export function ProjectNode({ data }: NodeProps) {
  const value = data as GraphNodeData
  return <div className="root-node"><span className="root-orbit">C</span><strong>{value.label}</strong><small>{value.branch_count ?? 0} 个本地分支</small><Handle type="source" position={Position.Right} /></div>
}

export function BranchNode({ data }: NodeProps) {
  const value = data as GraphNodeData
  const color = branchColors[value.branch_type || 'unknown']
  const blocked = value.status === 'blocked'
  return (
    <div className={`branch-node ${value.status === 'active' ? 'active-node' : ''} ${blocked ? 'blocked-node' : ''}`} style={{ '--branch-color': color } as React.CSSProperties} data-testid={`branch-node-${value.branch}`}>
      <Handle type="target" position={Position.Left} />
      <div className="branch-node-head"><span className="branch-glyph">⑂</span><strong>{value.label}</strong>{value.is_checked_out && <i title="已检出" />}</div>
      <code>{String(value.head_sha || '').slice(0, 8) || 'UNKNOWN'}</code>
      <div className="branch-node-meta"><span>{branchTypeLabels[value.branch_type || 'unknown']}</span><span>{branchStatusLabels[value.status || 'unknown']}</span></div>
      <div className="branch-task"><span>{value.task_name || '未维护'}</span>{typeof value.progress === 'number' && <b>{value.progress}%</b>}</div>
      <Handle type="source" position={Position.Right} />
    </div>
  )
}

export function TaskNode({ data }: NodeProps) {
  const value = data as GraphNodeData
  const color = branchColors[value.branch_type || 'unknown']
  const blockers = Array.isArray(value.blockers) ? value.blockers : []
  return (
    <div className={`task-node ${value.status === 'blocked' ? 'blocked-node' : ''}`} style={{ '--branch-color': color } as React.CSSProperties}>
      <Handle type="target" position={Position.Left} />
      <div className="task-node-status"><strong>{branchStatusLabels[value.status || 'unknown']}</strong>{typeof value.progress === 'number' && <b>{value.progress}%</b>}</div>
      <p>{value.label}</p>
      <small>{blockers.length ? `阻塞：${blockers[0]}` : `Coder: ${value.owner || '未维护'}`}</small>
    </div>
  )
}

export function CommitNode({ data }: NodeProps) {
  const value = data as GraphNodeData
  return <div className="commit-node" title={value.message || value.label}><Handle type="target" position={Position.Left} /><span>{value.label}</span><Handle type="source" position={Position.Right} /></div>
}

export function CollapsedNode({ data }: NodeProps) {
  const value = data as GraphNodeData
  return <div className="collapsed-node"><Handle type="target" position={Position.Left} />{value.label}<Handle type="source" position={Position.Right} /></div>
}
