import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { BranchDetailPanel } from '../src/components/BranchDetailPanel'
import { BranchTopologyGraph } from '../src/components/BranchTopologyGraph'
import { ProjectCard } from '../src/components/ProjectCard'
import { ProjectSidebar } from '../src/components/ProjectSidebar'
import { WorkspaceIssuePanel } from '../src/components/WorkspaceIssuePanel'
import { branch, graph, project, worktree } from './fixtures'

describe('核心界面组件', () => {
  it('渲染项目卡片与演示摘要', () => {
    render(<MemoryRouter><ProjectCard project={project} onEdit={vi.fn()} onDelete={vi.fn()} /></MemoryRouter>)
    expect(screen.getByText('Project Alpha')).toBeInTheDocument()
    expect(screen.getByText('Review demo results')).toBeInTheDocument()
    expect(screen.getByText('状态：Demo metadata')).toBeInTheDocument()
  })

  it('状态元数据缺失时显示未维护且测试为 NOT_RUN', () => {
    render(<BranchDetailPanel project={project} branch={branch} commit={null} />)
    expect(screen.getAllByText('未维护').length).toBeGreaterThan(2)
    expect(screen.getAllByText('NOT_RUN')).toHaveLength(3)
    expect(screen.getByText('Modified (2)')).toBeInTheDocument()
    expect(screen.getByText('src/example-dashboard.tsx')).toBeInTheDocument()
  })

  it('异常提醒可打开详情并优先显示脏工作区', () => {
    const select = vi.fn()
    const alerts = [
      ...Array.from({ length: 6 }, (_, index) => ({ alert_type: 'stale_branch', severity: 'attention' as const, message: `分支 ${index} 长期未提交`, branch_name: `feat/stale-${index}`, last_seen_at: '2026-08-16' })),
      { alert_type: 'dirty_worktree', severity: 'attention' as const, message: '工作区有变更', branch_name: 'feat/dashboard', last_seen_at: '2026-08-16' },
    ]
    render(<MemoryRouter><ProjectSidebar projects={[project]} selectedId={1} events={[]} alerts={alerts} onSelectAlert={select} /></MemoryRouter>)
    expect(screen.getByText('工作区有变更')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '查看异常详情：工作区有变更' }))
    expect(select).toHaveBeenCalledWith(alerts[6])
  })

  it('脏工作区总览可下钻到 Git 与文件详情', () => {
    const select = vi.fn()
    render(<WorkspaceIssuePanel worktrees={[worktree]} onSelectBranch={select} />)
    expect(screen.getByText('2')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '查看 feat/dashboard 工作区详情' }))
    expect(select).toHaveBeenCalledWith('feat/dashboard')
  })

  it('脱离 HEAD 的脏 Worktree 不会被误报为 Clean', () => {
    render(<WorkspaceIssuePanel worktrees={[{ ...worktree, path: 'example-workspace/detached', branch: 'DETACHED' }]} onSelectBranch={vi.fn()} />)
    expect(screen.getByText('DETACHED HEAD')).toBeInTheDocument()
    expect(screen.getByText('脱离 HEAD 工作区，请在本地处理')).toBeInTheDocument()
  })

  it('点击分支节点打开详情回调并可筛选分支', () => {
    const select = vi.fn()
    render(<div style={{ width: 1000, height: 700 }}><BranchTopologyGraph graph={graph} onSelectBranch={select} onSelectCommit={vi.fn()} /></div>)
    fireEvent.click(screen.getByTestId('branch-node-feat/dashboard'))
    expect(select).toHaveBeenCalledWith('feat/dashboard')
    fireEvent.change(screen.getByLabelText('搜索分支'), { target: { value: 'main' } })
    expect(screen.queryByTestId('branch-node-feat/dashboard')).not.toBeInTheDocument()
    expect(screen.getByTestId('branch-node-main')).toBeInTheDocument()
  })

  it('图谱可在焦点与全部分支之间按需切换', () => {
    const changeScope = vi.fn()
    render(<div style={{ width: 1000, height: 700 }}><BranchTopologyGraph graph={{ ...graph, visible_branches: 2, total_branches: 46 }} scope="focus" onScopeChange={changeScope} onSelectBranch={vi.fn()} onSelectCommit={vi.fn()} /></div>)
    expect(screen.getByText('已显示 2 / 46')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '查看全部分支' }))
    expect(changeScope).toHaveBeenCalledWith('all')
  })
})
