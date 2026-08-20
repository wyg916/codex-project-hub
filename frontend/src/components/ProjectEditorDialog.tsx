import { FormEvent, useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Project } from '../types/domain'

interface Props {
  open: boolean
  project?: Project | null
  onClose: () => void
  onSave: (payload: Record<string, unknown>) => Promise<void>
}

export function ProjectEditorDialog({ open, project, onClose, onSave }: Props) {
  const [form, setForm] = useState<Record<string, string>>({})
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    setForm(project ? {
      name: project.name,
      repo_path: project.repo_path,
      canonical_worktree: project.canonical_worktree,
      main_branch: project.main_branch,
      integration_branch: project.integration_branch || '',
      rc_branch: project.rc_branch || '',
      project_stage: project.project_stage,
    } : { repo_path: '', name: '', canonical_worktree: '', main_branch: '', integration_branch: '', rc_branch: '', project_stage: '未维护' })
    setError('')
  }, [open, project])

  if (!open) return null

  const set = (key: string, value: string) => setForm((current) => ({ ...current, [key]: value }))
  const pick = async () => {
    try {
      const result = await api.pickDirectory()
      if (result.path) set('repo_path', result.path)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '目录选择失败')
    }
  }
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setSaving(true)
    setError('')
    try {
      const payload = Object.fromEntries(Object.entries(form).filter(([, value]) => value !== ''))
      if (project) delete payload.repo_path
      await onSave(payload)
      onClose()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={onClose}>
      <form className="dialog" role="dialog" aria-modal="true" aria-label={project ? '编辑项目' : '新增项目'} onSubmit={submit} onMouseDown={(event) => event.stopPropagation()}>
        <div className="dialog-heading"><div><small>PROJECT REGISTRY</small><h2>{project ? '编辑项目配置' : '登记本地 Git 项目'}</h2></div><button type="button" className="icon-button" onClick={onClose}>×</button></div>
        {!project && <label>本地 Git 目录<div className="input-with-button"><input aria-label="本地 Git 目录" required value={form.repo_path || ''} onChange={(event) => set('repo_path', event.target.value)} placeholder="请选择 Project Alpha 的本地 Git 目录" /><button type="button" onClick={pick}>选择目录</button></div></label>}
        <label>显示名称<input value={form.name || ''} onChange={(event) => set('name', event.target.value)} placeholder="留空时自动使用目录名" /></label>
        <label>主项目目录<input value={form.canonical_worktree || ''} onChange={(event) => set('canonical_worktree', event.target.value)} placeholder="留空时自动识别" /></label>
        <div className="form-grid">
          <label>主分支<input value={form.main_branch || ''} onChange={(event) => set('main_branch', event.target.value)} placeholder="自动识别 main/master" /></label>
          <label>集成分支<input value={form.integration_branch || ''} onChange={(event) => set('integration_branch', event.target.value)} placeholder="可选" /></label>
          <label>RC 分支<input value={form.rc_branch || ''} onChange={(event) => set('rc_branch', event.target.value)} placeholder="可选" /></label>
        </div>
        <label>项目阶段<input value={form.project_stage || ''} onChange={(event) => set('project_stage', event.target.value)} /></label>
        {error && <p className="form-error" role="alert">{error}</p>}
        <div className="dialog-actions"><button type="button" onClick={onClose}>取消</button><button className="primary-button" disabled={saving}>{saving ? '校验并保存中…' : '校验并保存'}</button></div>
      </form>
    </div>
  )
}
