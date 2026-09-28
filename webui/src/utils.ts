export function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'medium' }).format(date)
}

export function formatDuration(value: number | null | undefined): string {
  if (value == null) return '—'
  if (value >= 1000) return `${(value / 1000).toFixed(2)} s`
  return `${value.toFixed(1)} ms`
}

export function shortId(value: string | null | undefined, size = 12): string {
  return value ? value.slice(0, size) : '—'
}
