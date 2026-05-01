import { describe, it, expect } from 'vitest'

describe('formatMemory', () => {
  const formatMemory = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)} KB`
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
  }

  it('格式化字节', () => {
    expect(formatMemory(100)).toBe('100 B')
  })

  it('格式化KB', () => {
    expect(formatMemory(2048)).toBe('2.00 KB')
  })

  it('格式化MB', () => {
    expect(formatMemory(5 * 1024 * 1024)).toBe('5.00 MB')
  })

  it('格式化GB', () => {
    expect(formatMemory(2 * 1024 * 1024 * 1024)).toBe('2.00 GB')
  })
})

describe('formatPercentage', () => {
  const formatPercentage = (value: number): string => `${value.toFixed(1)}%`

  it('格式化百分比', () => {
    expect(formatPercentage(85.678)).toBe('85.7%')
  })

  it('格式化0百分比', () => {
    expect(formatPercentage(0)).toBe('0.0%')
  })
})

describe('getMemoryPercentage', () => {
  const getMemoryPercentage = (used: number, total: number): number => {
    if (total === 0) return 0
    return (used / total) * 100
  }

  it('计算内存使用率', () => {
    expect(getMemoryPercentage(512, 1024)).toBe(50)
  })

  it('total为0返回0', () => {
    expect(getMemoryPercentage(512, 0)).toBe(0)
  })
})
