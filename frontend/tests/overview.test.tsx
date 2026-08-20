import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { OverviewPage } from '../src/pages/OverviewPage'

describe('项目总览', () => {
  afterEach(() => vi.restoreAllMocks())

  it('没有项目时显示空状态', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify([]), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    render(<MemoryRouter><OverviewPage /></MemoryRouter>)
    await waitFor(() => expect(screen.getByTestId('empty-projects')).toBeInTheDocument())
    expect(screen.getByText('还没有登记项目')).toBeInTheDocument()
  })
})
