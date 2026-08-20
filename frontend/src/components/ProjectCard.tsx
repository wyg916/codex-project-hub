import { useNavigate } from 'react-router-dom'
import type { Project } from '../types/domain'
import { compactLocalPath } from '../utils/paths'

export interface ProjectCardProps {
  project: Project
  onEdit: (project: Project) => void
  onDelete: (project: Project) => void
}

export function ProjectCard({ project, onEdit, onDelete }: ProjectCardProps) {
  const navigate = useNavigate()
  return (
    <article className="project-card" data-testid="project-card">
      <button className="card-main" onClick={() => navigate(`/projects/${project.id}`)}>
        <div className="card-title-row">
          <span className={`health-dot ${project.scan_status === 'ok' ? 'online' : 'danger'}`} />
          <div>
            <h3>{project.name}</h3>
            <p title={project.canonical_worktree}>{compactLocalPath(project.canonical_worktree)}</p>
          </div>
          <span className="stage-pill">{project.project_stage}</span>
        </div>
        <div className="branch-config">
          <span>主线 <strong>{project.main_branch}</strong></span>
          <span>集成 <strong>{project.integration_branch || '未设置'}</strong></span>
          <span>RC <strong>{project.rc_branch || '未设置'}</strong></span>
        </div>
        <div className="metric-grid">
          <span><strong>{project.overview.active}</strong>活跃</span>
          <span><strong>{project.overview.waiting_merge}</strong>待合并</span>
          <span className={project.overview.blocked ? 'danger-text' : ''}><strong>{project.overview.blocked}</strong>阻塞</span>
          <span className={project.overview.dirty ? 'warning-text' : ''}><strong>{project.overview.dirty}</strong>脏工作区</span>
        </div>
        <div className="next-action"><small>下一步优先事项</small><span>{project.overview.next_action}</span></div>
      </button>
      <div className="card-actions">
        <span className="metadata-state">状态：{project.overview.metadata_status}</span>
        <button onClick={() => onEdit(project)}>编辑</button>
        <button className="danger-button" onClick={() => onDelete(project)}>删除</button>
      </div>
    </article>
  )
}
