import type { Alert, Branch, GraphData, Project, ProjectEvent, Worktree } from '../types/domain'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  if (!response.ok) {
    let detail = `请求失败 (${response.status})`
    try {
      const payload = await response.json()
      detail = payload.detail ?? detail
    } catch {
      // Keep the status-based message.
    }
    throw new Error(detail)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const api = {
  listProjects: () => request<Project[]>('/api/projects'),
  getProject: (id: number) => request<Project>(`/api/projects/${id}`),
  createProject: (payload: Record<string, unknown>) => request<Project>('/api/projects', { method: 'POST', body: JSON.stringify(payload) }),
  updateProject: (id: number, payload: Record<string, unknown>) => request<Project>(`/api/projects/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteProject: (id: number) => request<void>(`/api/projects/${id}`, { method: 'DELETE' }),
  refreshProject: (id: number) => request(`/api/projects/${id}/refresh`, { method: 'POST' }),
  branches: (id: number) => request<Branch[]>(`/api/projects/${id}/branches`),
  worktrees: (id: number) => request<Worktree[]>(`/api/projects/${id}/worktrees`),
  graph: (id: number, scope: 'focus' | 'all' = 'focus') => request<GraphData>(`/api/projects/${id}/graph${scope === 'all' ? '?scope=all' : ''}`),
  events: (id: number) => request<ProjectEvent[]>(`/api/projects/${id}/events?limit=50`),
  alerts: (id: number) => request<Alert[]>(`/api/projects/${id}/alerts`),
  pickDirectory: () => request<{ path: string | null }>('/api/system/pick-directory', { method: 'POST' }),
  action: (name: string, payload: Record<string, unknown>) => request<Record<string, unknown>>(`/api/actions/${name}`, { method: 'POST', body: JSON.stringify(payload) }),
}
