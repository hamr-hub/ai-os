export interface GPUStatus {
  status: 'available' | 'unavailable'
  gpu_count: number
  name: string
  total_memory: number
  used_memory: number
  available_memory: number
  temperature: number
  utilization: number
  power_draw: number
  power_limit: number
  power_percent: number
  fan_speed: number
  clock_sm: number
  clock_mem: number
  memory_utilization: number
  primary?: GPUInfo
  all_gpus?: GPUInfo[]
  serverTime?: string
}

export interface GPUInfo {
  name: string
  total_memory: number
  used_memory: number
  available_memory: number
  temperature: number
  utilization: number
  power_draw: number
  power_limit: number
  power_percent: number
  fan_speed: number
  clock_sm: number
  clock_mem: number
  memory_utilization: number
}

export interface GPUSummary {
  status: 'available' | 'unavailable'
  current: GPUSummaryCurrent | null
  history: GPUHistoryEntry[]
}

export interface GPUSummaryCurrent {
  name: string
  gpu_count: number
  utilization: number
  temperature: number
  power_draw: number
  power_limit: number
  power_percent: number
  memory_utilization: number
  used_memory: number
  available_memory: number
  total_memory: number
  fan_speed?: number
}

export interface GPUHistoryEntry {
  timestamp: string
  utilization: number
  temperature: number
  power_draw: number
  power_percent: number
  memory_utilization: number
  used_memory: number
  available_memory: number
  total_memory: number
}

export interface ModelStatus {
  [modelName: string]: {
    running: boolean
    port: number | null
    service: string | null
    active_requests: number
    preloaded: boolean
    last_used: string | null
  }
}

export interface ModelInfo {
  id: string
  object: string
  created: number
  owned_by: string
}

export interface ModelsResponse {
  object: string
  data: ModelInfo[]
}

export interface ActionResponse {
  status: string
  model?: string
  message?: string
}
