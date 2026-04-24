/**
 * 根据百分比获取进度条颜色变量
 */
export const getProgressColor = (pct: number) => {
  if (pct >= 90) return 'var(--color-danger)'
  if (pct >= 70) return 'var(--color-warning)'
  return 'var(--color-success)'
}

/**
 * 根据数值获取状态等级 (success, warning, danger)
 */
export const getStatusLevel = (value: number, warn = 70, danger = 90) => {
  if (value >= danger) return 'danger'
  if (value >= warn) return 'warning'
  return 'success'
}

/**
 * 获取健康状态的视觉配置
 */
export const getHealthStatusConfig = (status: string) => {
  const configs: Record<string, { bg: string; color: string; label: string }> = {
    healthy: { bg: 'rgba(34, 197, 94, 0.1)', color: '#22c55e', label: '健康' },
    degraded: { bg: 'rgba(245, 158, 11, 0.1)', color: '#f59e0b', label: '降级' },
    warning: { bg: 'rgba(245, 158, 11, 0.1)', color: '#f59e0b', label: '降级' },
    critical: { bg: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', label: '异常' },
    error: { bg: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', label: '异常' },
  }
  return configs[status] || configs.critical
}
