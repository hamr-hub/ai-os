import { computed } from 'vue'
import type { Ref } from 'vue'
import type { GPUHistoryEntry } from '@/types'

interface DatasetOption {
  label: string
  extract: (e: GPUHistoryEntry) => number
  borderColor: string
  backgroundColor: string
  fill?: boolean
  borderWidth?: number
}

export function createDataset(
  history: Ref<GPUHistoryEntry[]>,
  option: DatasetOption
) {
  return computed(() => [
    {
      label: option.label,
      data: history.value.map(option.extract),
      borderColor: option.borderColor,
      backgroundColor: option.backgroundColor,
      fill: option.fill ?? true,
      tension: 0.4,
      pointRadius: 0,
      borderWidth: option.borderWidth ?? 2,
    },
  ])
}

export function useGPUChartDatasets(gpuHistory: Ref<GPUHistoryEntry[]>) {
  const gpuTimeLabels = computed(() =>
    gpuHistory.value.map((e) => {
      const d = new Date(e.timestamp)
      return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    })
  )

  const gpuUtilDataset = createDataset(gpuHistory, {
    label: 'GPU 利用率',
    extract: (e) => e.utilization,
    borderColor: '#6366f1',
    backgroundColor: 'rgba(99, 102, 241, 0.08)',
  })

  const gpuTempDataset = createDataset(gpuHistory, {
    label: 'GPU 温度',
    extract: (e) => e.temperature,
    borderColor: '#f59e0b',
    backgroundColor: 'rgba(245, 158, 11, 0.08)',
  })

  const gpuMemDataset = createDataset(gpuHistory, {
    label: '显存利用率',
    extract: (e) => e.memory_utilization,
    borderColor: '#06b6d4',
    backgroundColor: 'rgba(6, 182, 212, 0.08)',
  })

  const gpuPowerDataset = createDataset(gpuHistory, {
    label: '功耗',
    extract: (e) => e.power_percent ?? e.power_draw,
    borderColor: '#ef4444',
    backgroundColor: 'rgba(239, 68, 68, 0.08)',
  })

  const vllmRunningDataset = createDataset(gpuHistory, {
    label: '运行请求',
    extract: (e) => e.vllm_running_requests ?? 0,
    borderColor: '#22c55e',
    backgroundColor: 'rgba(34, 197, 94, 0.08)',
  })

  const vllmWaitingDataset = createDataset(gpuHistory, {
    label: '等待请求',
    extract: (e) => e.vllm_waiting_requests ?? 0,
    borderColor: '#f59e0b',
    backgroundColor: 'rgba(245, 158, 11, 0.08)',
  })

  const vllmGpuCacheDataset = createDataset(gpuHistory, {
    label: 'KV 缓存使用',
    extract: (e) => e.vllm_gpu_cache_usage ?? 0,
    borderColor: '#8b5cf6',
    backgroundColor: 'rgba(139, 92, 246, 0.08)',
  })

  const gpuMultiDataset = computed(() => [
    {
      label: '利用率 (%)',
      data: gpuHistory.value.map((e) => e.utilization),
      borderColor: '#6366f1',
      backgroundColor: 'rgba(99, 102, 241, 0.08)',
      fill: true,
      tension: 0.4,
      pointRadius: 0,
      borderWidth: 2,
    },
    {
      label: '温度 (°C)',
      data: gpuHistory.value.map((e) => e.temperature),
      borderColor: '#f59e0b',
      backgroundColor: 'rgba(245, 158, 11, 0.05)',
      fill: false,
      tension: 0.4,
      pointRadius: 0,
      borderWidth: 1.5,
    },
    {
      label: '显存 (%)',
      data: gpuHistory.value.map((e) => e.memory_utilization),
      borderColor: '#06b6d4',
      backgroundColor: 'rgba(6, 182, 212, 0.05)',
      fill: false,
      tension: 0.4,
      pointRadius: 0,
      borderWidth: 1.5,
    },
  ])

  return {
    gpuTimeLabels,
    gpuUtilDataset,
    gpuTempDataset,
    gpuMemDataset,
    gpuPowerDataset,
    vllmRunningDataset,
    vllmWaitingDataset,
    vllmGpuCacheDataset,
    gpuMultiDataset,
  }
}
