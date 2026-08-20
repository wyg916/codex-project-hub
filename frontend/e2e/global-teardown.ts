import { cleanupRuntime, stopServer, waitForHealth } from './runtime'

export default async function globalTeardown() {
  try {
    stopServer()
    await waitForHealth(false)
  } finally {
    if (process.env.CPC_KEEP_E2E_ARTIFACTS !== '1') cleanupRuntime()
  }
}
