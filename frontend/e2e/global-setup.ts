import { prepareRuntime, startServer } from './runtime'

export default async function globalSetup() {
  prepareRuntime()
  await startServer()
}
