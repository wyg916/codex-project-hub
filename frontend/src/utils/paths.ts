export function compactLocalPath(value: string | null | undefined, fallback = '未检出'): string {
  if (!value) return fallback
  const normalized = value.replace(/[\\/]+$/, '')
  const segments = normalized.split(/[\\/]/).filter(Boolean)
  const leaf = segments.at(-1)
  return leaf ? `…/${leaf}` : fallback
}
