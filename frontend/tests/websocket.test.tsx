import { act, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { ProjectDashboard } from '../src/pages/ProjectDashboard'
import { branch, graph, project, worktree } from './fixtures'

class MockWebSocket {
  static instance: MockWebSocket
  onopen: (() => void) | null = null
  onmessage: ((event: { data: string }) => void) | null = null
  onerror: (() => void) | null = null
  onclose: (() => void) | null = null
  constructor() {
    MockWebSocket.instance = this
    queueMicrotask(() => this.onopen?.())
  }
  close() { this.onclose?.() }
  sendMessage(payload: unknown) { this.onmessage?.({ data: JSON.stringify(payload) }) }
}

describe('WebSocket 实时更新', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('收到 branch.updated 后重新读取并更新图谱', async () => {
    let updated = false
    vi.stubGlobal('WebSocket', MockWebSocket)
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input)
      let value: unknown
      if (url === '/api/projects') value = [project]
      else if (url.endsWith('/branches')) value = [branch]
      else if (url.endsWith('/worktrees')) value = [worktree]
      else if (url.endsWith('/graph')) value = updated ? { ...graph, nodes: graph.nodes.map((node) => node.id === 'branch:feat/dashboard' ? { ...node, data: { ...node.data, task_name: 'Example WebSocket Task' } } : node) } : graph
      else if (url.endsWith('/events?limit=50') || url.endsWith('/alerts')) value = []
      else value = project
      return new Response(JSON.stringify(value), { status: 200, headers: { 'Content-Type': 'application/json' } })
    })
    render(<MemoryRouter initialEntries={['/projects/1']}><Routes><Route path="/projects/:projectId" element={<ProjectDashboard />} /></Routes></MemoryRouter>)
    await screen.findByTestId('branch-node-feat/dashboard')
    expect(screen.queryByText('Example WebSocket Task')).not.toBeInTheDocument()
    updated = true
    await act(async () => MockWebSocket.instance.sendMessage({ type: 'branch.updated' }))
    await waitFor(() => expect(screen.getByText('Example WebSocket Task')).toBeInTheDocument())
  })

  it('慢图谱不阻塞项目驾驶舱骨架和 Git 事实', async () => {
    vi.stubGlobal('WebSocket', MockWebSocket)
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input)
      if (url.endsWith('/graph')) return new Promise<Response>(() => undefined)
      let value: unknown
      if (url === '/api/projects') value = [project]
      else if (url.endsWith('/branches')) value = [branch]
      else if (url.endsWith('/worktrees')) value = [worktree]
      else if (url.endsWith('/events?limit=50') || url.endsWith('/alerts')) value = []
      else value = project
      return new Response(JSON.stringify(value), { status: 200, headers: { 'Content-Type': 'application/json' } })
    })
    render(<MemoryRouter initialEntries={['/projects/1']}><Routes><Route path="/projects/:projectId" element={<ProjectDashboard />} /></Routes></MemoryRouter>)
    expect(await screen.findByRole('heading', { name: 'Project Alpha' })).toBeVisible()
    expect(screen.getByText('正在生成压缩图谱…')).toBeVisible()
    expect(screen.getByTestId('dirty-summary')).toHaveTextContent('1 异常 · 查看')
  })
})
