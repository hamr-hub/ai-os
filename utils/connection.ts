export type StreamTarget = 'manage' | 'inference'
export type ConnectionStatus = 'checking' | 'online' | 'degraded' | 'offline'

export interface EndpointProbeStatus {
  ok: boolean
  status?: number
  error?: string
}

export interface ConnectionDetailsLike {
  manage: EndpointProbeStatus
  inference: EndpointProbeStatus
}

const formatProbeError = (result: EndpointProbeStatus) => {
  if (result.error) return result.error
  if (typeof result.status === 'number') return `HTTP ${result.status}`
  return '连接失败'
}

export const getConnectionIssueMessage = (
  target: StreamTarget,
  status: ConnectionStatus,
  details: ConnectionDetailsLike,
  fallback?: string | null
) => {
  const targetLabel = target === 'manage' ? '管理接口' : '推理接口'
  const targetProbe = target === 'manage' ? details.manage : details.inference

  if (!targetProbe.ok) {
    return `${targetLabel}不可用: ${formatProbeError(targetProbe)}`
  }

  if (status === 'degraded') {
    const otherLabel = target === 'manage' ? '推理接口' : '管理接口'
    const otherProbe = target === 'manage' ? details.inference : details.manage
    if (!otherProbe.ok) {
      return `${otherLabel}异常，但当前${targetLabel}仍可用`
    }
  }

  return fallback || `${targetLabel}状态异常`
}

export const buildStreamErrorMessage = (
  baseMessage: string,
  target: StreamTarget,
  status: ConnectionStatus,
  details: ConnectionDetailsLike,
  fallback?: string | null
) => {
  if (status === 'online') {
    return baseMessage
  }

  const connectionIssue = getConnectionIssueMessage(target, status, details, fallback)
  if (!connectionIssue) {
    return baseMessage
  }

  return `${baseMessage}。${connectionIssue}`
}
