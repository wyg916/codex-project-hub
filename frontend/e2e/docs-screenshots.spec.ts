import { expect, test, type Page } from '@playwright/test'
import { mkdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { projectRoot, repoPath, writeStatusMetadata } from './runtime'

const captureDocs = process.env.CPC_CAPTURE_DOCS === '1'
const imageDirectory = join(projectRoot, 'docs', 'images')

async function captureWebpScreenshot(page: Page): Promise<Buffer> {
  const png = await page.screenshot({
    animations: 'disabled',
    caret: 'hide',
    fullPage: true,
    scale: 'css',
    type: 'png',
  })
  const dataUrl = await page.evaluate(async (pngBase64) => {
    const image = new Image()
    image.src = `data:image/png;base64,${pngBase64}`
    await image.decode()
    const canvas = document.createElement('canvas')
    canvas.width = image.naturalWidth
    canvas.height = image.naturalHeight
    const context = canvas.getContext('2d')
    if (!context) throw new Error('Canvas 2D context is unavailable')
    context.drawImage(image, 0, 0)
    return canvas.toDataURL('image/webp', 0.86)
  }, png.toString('base64'))
  const prefix = 'data:image/webp;base64,'
  if (!dataUrl.startsWith(prefix)) throw new Error('Chromium could not encode the screenshot as WebP')
  return Buffer.from(dataUrl.slice(prefix.length), 'base64')
}

test('capture privacy-safe documentation screenshots from the running app', async ({ page }) => {
  test.skip(!captureDocs, 'Set CPC_CAPTURE_DOCS=1 to regenerate tracked documentation screenshots.')
  mkdirSync(imageDirectory, { recursive: true })
  await page.setViewportSize({ width: 1920, height: 1080 })
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
  const overviewImage = await captureWebpScreenshot(page)

  writeStatusMetadata()
  await card.locator('.card-main').click()
  await expect(page.getByTestId('topology-graph')).toBeVisible()
  await page.getByTestId('branch-node-feat/example-dashboard').click()
  await expect(page.getByTestId('branch-detail')).toContainText('Example Dashboard Task', { timeout: 10_000 })
  const dashboardImage = await captureWebpScreenshot(page)

  // Only replace the public pair after both real views were captured successfully.
  writeFileSync(join(imageDirectory, 'dashboard-overview.webp'), overviewImage)
  writeFileSync(join(imageDirectory, 'project-dashboard.webp'), dashboardImage)
})
