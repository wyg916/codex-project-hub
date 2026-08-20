import { execFileSync, spawn } from 'node:child_process'
import { closeSync, existsSync, mkdirSync, openSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'

export const projectRoot = resolve(import.meta.dirname, '..', '..')
export const runtimeRoot = join(tmpdir(), 'codex-project-hub-e2e-runtime')
export const repoPath = join(runtimeRoot, 'Project Alpha')
export const worktreePath = join(runtimeRoot, 'Example Workspace')
export const dataPath = join(runtimeRoot, 'app-data')
export const testPort = 18765
const testBaseUrl = `http://127.0.0.1:${testPort}`
const pidPath = join(runtimeRoot, 'server.pid')
const stdoutPath = join(runtimeRoot, 'server.out.log')
const stderrPath = join(runtimeRoot, 'server.err.log')
const healthTimeoutMs = 30_000
const healthPollMs = 250
const maxDiagnosticChars = 2_000

interface ManagedChildProcess {
  pid?: number
  exitCode: number | null
  signalCode: string | null
  once: (event: 'error', listener: (error: Error) => void) => unknown
  unref: () => void
}

interface HealthWaitOptions {
  child?: ManagedChildProcess
  getSpawnError?: () => Error | null
  timeoutMs?: number
}

export function sanitizeServerDiagnostic(value: string): string {
  const redacted = value
    .replace(/\u001b\[[0-9;]*m/g, '')
    .replace(/(^|[\s"'(])(?:[A-Za-z]:[\\/])[^ \r\n"']+/gm, '$1<REDACTED_PATH>')
    .replace(/\/(?:Users|home)\/[^/\s]+(?:\/[^\s]*)?/g, '<REDACTED_PATH>')
    .replace(/([a-z][a-z0-9+.-]*:\/\/)[^/\s:@]+:[^@\s/]+@/gi, '$1<REDACTED_CREDENTIALS>@')
    .replace(/\b(?:github_pat_|gh[pousr]_)[A-Za-z0-9_]{20,}\b/gi, '<REDACTED_SECRET>')
    .replace(/\b(password|passwd|token|secret|api[_-]?key)\b\s*[:=]\s*["']?[^,\s"']+/gi, '$1=<REDACTED>')
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, '<REDACTED_EMAIL>')
    .trim()
  return redacted.slice(-maxDiagnosticChars)
}

function readServerDiagnostics(): string {
  const read = (path: string) => {
    try {
      return readFileSync(path, 'utf8')
    } catch {
      return ''
    }
  }
  const diagnostics = sanitizeServerDiagnostic(`stderr:\n${read(stderrPath)}\nstdout:\n${read(stdoutPath)}`)
  return diagnostics || 'No server diagnostics were captured.'
}

function startupFailure(reason: string): Error {
  return new Error(`${sanitizeServerDiagnostic(reason)}\n${readServerDiagnostics()}`)
}

function git(cwd: string, ...args: string[]): string {
  return execFileSync('git', args, { cwd, encoding: 'utf8', windowsHide: true }).trim()
}

export function prepareRuntime(): void {
  assertSafeRuntimeRoot()
  if (existsSync(runtimeRoot)) rmSync(runtimeRoot, { recursive: true, force: true })
  mkdirSync(repoPath, { recursive: true })
  git(repoPath, 'init', '-b', 'main')
  git(repoPath, 'config', 'user.name', 'Example Developer')
  git(repoPath, 'config', 'user.email', 'developer@example.invalid')
  writeFileSync(join(repoPath, 'README.md'), 'E2E base\n', 'utf8')
  git(repoPath, 'add', 'README.md')
  git(repoPath, 'commit', '-m', 'initial')
  git(repoPath, 'branch', 'feat/example-dashboard')
  git(repoPath, 'branch', 'fix/example-alert')
  git(repoPath, 'branch', 'integration/example')
  git(repoPath, 'branch', 'release/example-rc')
  git(repoPath, 'worktree', 'add', worktreePath, 'feat/example-dashboard')
  git(worktreePath, 'config', 'user.name', 'Example Developer')
  git(worktreePath, 'config', 'user.email', 'developer@example.invalid')
  writeFileSync(join(worktreePath, 'feature.txt'), 'feature base\n', 'utf8')
  git(worktreePath, 'add', 'feature.txt')
  git(worktreePath, 'commit', '-m', 'feature baseline')
  mkdirSync(dataPath, { recursive: true })
}

function assertSafeRuntimeRoot(): void {
  if (dirname(runtimeRoot) !== resolve(tmpdir()) || runtimeRoot === resolve(tmpdir())) {
    throw new Error('Unsafe E2E runtime path')
  }
}

export function cleanupRuntime(): void {
  assertSafeRuntimeRoot()
  if (existsSync(runtimeRoot)) rmSync(runtimeRoot, { recursive: true, force: true })
}

function readPid(): number | null {
  if (!existsSync(pidPath)) return null
  const value = Number(readFileSync(pidPath, 'utf8').trim())
  return Number.isInteger(value) && value > 0 ? value : null
}

export function stopServer(): void {
  const pid = readPid()
  if (!pid) return
  try {
    const commandLine = execFileSync('powershell.exe', ['-NoProfile', '-Command', `(Get-CimInstance Win32_Process -Filter "ProcessId = ${pid}").CommandLine`], { encoding: 'utf8', windowsHide: true })
    if (commandLine.includes('uvicorn') && commandLine.includes('backend.app.main:app')) process.kill(pid)
  } catch {
    // The managed test server is already stopped.
  }
}

export async function startServer(): Promise<void> {
  await waitForHealth(false)
  const python = join(projectRoot, '.venv', 'Scripts', 'python.exe')
  const stdoutFd = openSync(stdoutPath, 'a')
  const stderrFd = openSync(stderrPath, 'a')
  let child: ManagedChildProcess
  try {
    child = spawn(python, ['-m', 'uvicorn', 'backend.app.main:app', '--host', '127.0.0.1', '--port', String(testPort), '--ws-max-size', '1024', '--ws-max-queue', '8'], {
      cwd: projectRoot,
      detached: true,
      windowsHide: true,
      stdio: ['ignore', stdoutFd, stderrFd],
      env: {
        ...process.env,
        CPC_DATA_DIR: dataPath,
        CPC_SCAN_INTERVAL: '1',
        CPC_ENABLE_SYSTEM_ACTIONS: '0',
        CPC_ALLOWED_ORIGINS: testBaseUrl,
      },
    })
  } finally {
    closeSync(stdoutFd)
    closeSync(stderrFd)
  }
  let spawnError: Error | null = null
  child.once('error', (error: Error) => { spawnError = error })
  if (!child.pid) throw startupFailure('Failed to start the E2E server process.')
  child.unref()
  writeFileSync(pidPath, String(child.pid), 'utf8')
  try {
    await waitForHealth(true, { child, getSpawnError: () => spawnError })
  } catch (error) {
    stopServer()
    throw error
  }
}

export async function waitForHealth(expected: boolean, options: HealthWaitOptions = {}): Promise<void> {
  const timeoutMs = options.timeoutMs ?? healthTimeoutMs
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const spawnError = options.getSpawnError?.()
    if (spawnError) throw startupFailure(`E2E server process error: ${spawnError.message}`)
    if (options.child && (options.child.exitCode !== null || options.child.signalCode !== null)) {
      throw startupFailure(`E2E server exited before readiness (code=${options.child.exitCode ?? 'none'}, signal=${options.child.signalCode ?? 'none'}).`)
    }
    let healthy = false
    try {
      const response = await fetch(`${testBaseUrl}/api/health`)
      healthy = response.ok
    } catch {
      healthy = false
    }
    if (healthy === expected) return
    await new Promise((resolvePromise) => setTimeout(resolvePromise, Math.min(healthPollMs, Math.max(1, deadline - Date.now()))))
  }
  const reason = `E2E server health did not become ${expected} within ${timeoutMs}ms.`
  throw expected ? startupFailure(reason) : new Error(reason)
}

export async function restartServer(): Promise<void> {
  stopServer()
  await waitForHealth(false)
  await startServer()
}

export function commitFeatureChange(): string {
  writeFileSync(join(worktreePath, 'feature.txt'), `updated ${Date.now()}\n`, 'utf8')
  git(worktreePath, 'add', 'feature.txt')
  git(worktreePath, 'commit', '-m', 'e2e live update')
  return git(worktreePath, 'rev-parse', '--short=8', 'HEAD')
}

export function makeDirtyWorktree(): void {
  writeFileSync(join(worktreePath, 'dirty-e2e.txt'), 'dirty\n', 'utf8')
}

export function makeDetachedDirtyWorktree(): void {
  const detachedPath = join(runtimeRoot, 'Detached Example')
  git(repoPath, 'worktree', 'add', '--detach', detachedPath, 'HEAD')
  writeFileSync(join(detachedPath, 'detached-dirty.txt'), 'dirty\n', 'utf8')
}

export function writeStatusMetadata(): void {
  const commonRaw = git(repoPath, 'rev-parse', '--git-common-dir')
  const common = resolve(repoPath, commonRaw)
  const folder = join(common, 'codex-dashboard')
  mkdirSync(folder, { recursive: true })
  writeFileSync(join(folder, 'status.json'), JSON.stringify({
    schema_version: 1,
    project: { display_name: 'Project Alpha', canonical_worktree: repoPath, main_branch: 'main', integration_branch: 'integration/example', rc_branch: 'release/example-rc' },
    branches: {
      'feat/example-dashboard': {
        branch_type: 'feature', task_name: 'Example Dashboard Task', objective: 'Validate the demo refresh workflow', codex_task_id: 'EXAMPLE-1', codex_session_title: 'Example E2E', owner: 'Example Developer', status: 'validating', phase: 'acceptance', result: 'PARTIAL', progress_mode: 'weighted', phase_progress: { requirement: 100, design: 100, development: 100, unit_test: 100, integration_test: 80, acceptance: 60, merge: 0 }, tests: { unit: 'PASS', integration: 'PASS', e2e: 'RUNNING' }, blockers: [], next_actions: ['Complete demo acceptance'], updated_at: new Date().toISOString(),
      },
    },
  }, null, 2), 'utf8')
}
