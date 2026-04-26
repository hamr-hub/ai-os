/**
 * 格式化字节数为可读字符串
 */
export const formatBytes = (bytes: number) => {
  if (!bytes) return '0 GB'
  if (bytes < 1024) return `${bytes} B`
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`
}

/**
 * 格式化 Token 数量（K, M 单位）
 */
export const formatTokens = (n: number): string => {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return `${n}`
}

/**
 * 格式化时间标签
 */
export const formatTimeLabel = (ts: string) => {
  if (!ts) return ''
  const d = new Date(ts)
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

/**
 * 格式化相对时间
 */
export const formatRelativeTime = (ts?: string | null) => {
  if (!ts) return '暂无更新'

  const date = new Date(ts)
  const time = date.getTime()
  if (Number.isNaN(time)) return '暂无更新'

  const diffMs = Date.now() - time
  if (diffMs < 0) return `刚刚 ${formatTimeLabel(ts)}`

  const diffMinutes = Math.floor(diffMs / 60000)
  if (diffMinutes < 1) return `刚刚 ${formatTimeLabel(ts)}`
  if (diffMinutes < 60) return `${diffMinutes}分钟前`

  const diffHours = Math.floor(diffMinutes / 60)
  if (diffHours < 24) return `${diffHours}小时前`

  return formatTimeLabel(ts)
}
