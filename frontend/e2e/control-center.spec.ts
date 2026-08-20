import { expect, test } from '@playwright/test'
import { commitFeatureChange, makeDetachedDirtyWorktree, makeDirtyWorktree, repoPath, restartServer, writeStatusMetadata } from './runtime'

test.describe.configure({ mode: 'serial' })

test('演示项目登记、图谱、5秒更新、状态元数据与重启持久化', async ({ page, context }) => {
  const consoleErrors: string[] = []
  page.on('console', (message) => { if (message.type() === 'error') consoleErrors.push(message.text()) })
  page.on('pageerror', (error) => consoleErrors.push(error.message))

  await page.goto('/')
  await page.getByRole('button', { name: '＋ 新增项目' }).click()
  await page.getByLabel('本地 Git 目录').fill(repoPath)
  await page.getByLabel('显示名称').fill('Project Alpha')
  await page.getByLabel('主分支').fill('main')
  await page.getByLabel('集成分支').fill('integration/example')
  await page.getByLabel('RC 分支').fill('release/example-rc')
  await page.getByRole('button', { name: '校验并保存' }).click()
  const card = page.getByTestId('project-card').filter({ hasText: 'Project Alpha' })
  await expect(card).toBeVisible({ timeout: 15_000 })
  await card.locator('.card-main').click()
  await expect(page).toHaveURL(/\/projects\/\d+/)
  await expect(page.getByTestId('topology-graph')).toBeVisible()
  await expect(page.getByTestId('branch-node-main')).toBeVisible()
  await expect(page.getByTestId('branch-node-feat/example-dashboard')).toBeVisible()

  await page.getByTestId('branch-node-feat/example-dashboard').click()
  await expect(page.getByTestId('branch-detail')).toContainText('feat/example-dashboard')
  const head = commitFeatureChange()
  await expect(page.getByTestId('branch-detail')).toContainText(head, { timeout: 5_000 })

  makeDirtyWorktree()
  await expect(page.getByTestId('branch-detail')).toContainText('dirty-e2e.txt', { timeout: 5_000 })
  await expect(page.getByTestId('branch-detail')).toContainText('Modified (1)')
  await page.getByTestId('dirty-summary').click()
  await expect(page.getByTestId('dirty-worktree-detail')).toContainText('个异常工作区')
  await page.screenshot({ path: 'test-results/screenshots/dirty-worktree-detail.png', fullPage: true })
  await page.getByRole('button', { name: '查看 feat/example-dashboard 工作区详情' }).click()
  await expect(page.getByTestId('branch-detail')).toContainText('dirty-e2e.txt')
  makeDetachedDirtyWorktree()
  await expect(page.getByTestId('dirty-summary')).toContainText('2 异常', { timeout: 10_000 })
  await page.getByTestId('dirty-summary').click()
  await expect(page.getByTestId('dirty-worktree-detail')).toContainText('DETACHED HEAD')
  await expect(page.getByTestId('dirty-worktree-detail')).toContainText('脱离 HEAD 工作区，请在本地处理')
  await page.getByRole('button', { name: '查看 feat/example-dashboard 工作区详情' }).click()
  writeStatusMetadata()
  await expect(page.getByTestId('branch-detail')).toContainText('Example Dashboard Task', { timeout: 5_000 })
  await expect(page.getByTestId('branch-detail')).toContainText('Complete demo acceptance')

  const savedUrl = page.url()
  expect(consoleErrors).toEqual([])
  await page.close()
  await restartServer()
  const resumed = await context.newPage()
  const resumedErrors: string[] = []
  resumed.on('console', (message) => { if (message.type() === 'error') resumedErrors.push(message.text()) })
  resumed.on('pageerror', (error) => resumedErrors.push(error.message))
  await resumed.goto(savedUrl)
  await expect(resumed.getByText('Project Alpha', { exact: true }).first()).toBeVisible()
  await expect(resumed.getByTestId('branch-node-feat/example-dashboard')).toBeVisible()
  expect(resumedErrors).toEqual([])
})

for (const viewport of [
  { name: '1366x768', width: 1366, height: 768 },
  { name: '1920x1080', width: 1920, height: 1080 },
  { name: '2560x1440', width: 2560, height: 1440 },
]) {
  test(`分辨率 ${viewport.name} 无失控横向溢出`, async ({ page }) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height })
    await page.goto('/')
    const card = page.getByTestId('project-card').filter({ hasText: 'Project Alpha' })
    await card.locator('.card-main').click()
    await expect(page.getByTestId('topology-graph')).toBeVisible()
    const dimensions = await page.evaluate(() => ({ body: document.body.scrollWidth, viewport: document.documentElement.clientWidth }))
    expect(dimensions.body).toBeLessThanOrEqual(dimensions.viewport)
    await page.screenshot({ path: `test-results/screenshots/${viewport.name}.png`, fullPage: true })
  })
}
