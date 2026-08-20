import { describe, expect, it } from 'vitest'
import { sanitizeServerDiagnostic, waitForHealth } from '../e2e/runtime'

describe('E2E runtime diagnostics', () => {
  it('redacts paths, credentials, tokens, and email addresses', () => {
    const localPath = ['C:', 'Users', 'Example', 'Project Alpha'].join('\\')
    const token = `ghp_${'A'.repeat(36)}`
    const passwordValue = ['demo', 'password'].join('-')
    const diagnostic = `failure at ${localPath} password=${passwordValue} ${token} developer@example.invalid`

    const sanitized = sanitizeServerDiagnostic(diagnostic)

    expect(sanitized).toContain('<REDACTED_PATH>')
    expect(sanitized).toContain('<REDACTED_SECRET>')
    expect(sanitized).toContain('<REDACTED_EMAIL>')
    expect(sanitized).not.toContain(localPath)
    expect(sanitized).not.toContain(passwordValue)
    expect(sanitized).not.toContain(token)
  })

  it('keeps only the diagnostic tail', () => {
    expect(sanitizeServerDiagnostic('x'.repeat(2_500))).toHaveLength(2_000)
  })

  it('fails immediately when the managed server exits before readiness', async () => {
    const exitedChild = {
      pid: 123,
      exitCode: 1,
      signalCode: null,
      once: () => exitedChild,
      unref: () => undefined,
    }

    await expect(waitForHealth(true, { child: exitedChild, timeoutMs: 30_000 }))
      .rejects.toThrow('E2E server exited before readiness')
  })
})
