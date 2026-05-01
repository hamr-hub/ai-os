import { describe, expect, it } from 'vitest'
import { buildStreamErrorMessage, getConnectionIssueMessage } from '@/utils/connection'

const degradedDetails = {
  manage: { ok: true, status: 200 },
  inference: { ok: false, status: 503, error: 'HTTP 503' },
}

describe('connection utils', () => {
  it('为不可用的推理接口生成明确提示', () => {
    const message = getConnectionIssueMessage('inference', 'degraded', degradedDetails, null)

    expect(message).toContain('推理接口不可用')
    expect(message).toContain('HTTP 503')
  })

  it('在线状态下保留原始流式错误', () => {
    const message = buildStreamErrorMessage('请求超时', 'manage', 'online', degradedDetails, null)

    expect(message).toBe('请求超时')
  })

  it('降级状态下拼接连接上下文', () => {
    const message = buildStreamErrorMessage('流式请求失败', 'inference', 'degraded', degradedDetails, null)

    expect(message).toContain('流式请求失败')
    expect(message).toContain('推理接口不可用')
  })
})
