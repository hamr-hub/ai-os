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

export const formatDownloadSpeed = (mbps: number): string => {
  if (!mbps || mbps <= 0) return '--'
  if (mbps >= 1024) return `${(mbps / 1024).toFixed(1)} GB/s`
  return `${mbps.toFixed(1)} MB/s`
}

export const formatRemainingTime = (seconds: number): string => {
  if (!seconds || seconds <= 0) return '--'
  if (seconds < 60) return `${Math.round(seconds)}秒`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}分${Math.round(seconds % 60)}秒`
  return `${Math.floor(seconds / 3600)}时${Math.floor((seconds % 3600) / 60)}分`
}

export const formatDownloadProgress = (pct: number): string => {
  if (!pct || pct < 0) return '0%'
  if (pct >= 100) return '100%'
  return `${pct.toFixed(1)}%`
}

export const formatModelSize = (sizeB: number | null): string => {
  if (!sizeB) return '--'
  if (sizeB >= 1) return `${sizeB}B`
  return '--'
}

export const formatQuantType = (quant: string | null): string => {
  if (!quant) return 'fp16'
  return quant
}

export const formatMemoryEstimate = (gb: number | null): string => {
  if (!gb) return '--'
  return `${gb.toFixed(1)} GB`
}

export const formatSource = (source: string): string => {
  const map: Record<string, string> = {
    hf: 'HuggingFace',
    modelscope: 'ModelScope',
    openxlab: 'OpenXLab',
    local: '本地',
  }
  return map[source] || source
}
