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
    supports_images?: boolean
    supports_tool_calling?: boolean
    supports_image_generation?: boolean
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

export interface TestCapabilityResult {
  status: string
  message: string
  latency_ms?: number
  error?: string
}

export interface TestReport {
  model_name: string
  test_timestamp: string
  overall_status: string
  feature_support: {
    chat: boolean
    tool_calling: boolean
    image: boolean
    multimodal: boolean
    image_generation: boolean
  }
  performance_metrics?: {
    chat?: { avg_tps: number; avg_latency: number; avg_token_count: number; tests_passed: number }
    image?: { avg_tps: number; avg_latency: number; tests_passed: number }
    overall?: {
      avg_tps: number
      avg_latency: number
      tests_passed: number
      tests_total: number
      pass_rate: number
    }
  }
  resource_utilization?: {
    test_duration_seconds?: number
    gpu?: {
      available: boolean
      start_utilization: number
      end_utilization: number
      start_memory_used_mb: number
      end_memory_used_mb: number
      start_temperature: number
      end_temperature: number
      end_utilization_pct?: number
    }
    memory?: { start_used_mb: number; end_used_mb: number; delta_mb: number }
  }
  test_results?: {
    test_name: string
    feature_type: string
    status: string
    duration?: number
    metrics?: Record<string, any>
    error?: string
    details?: string
  }[]
  errors?: string[]
  warnings?: string[]
}

export interface TestResponse {
  status: string
  message: string
  report?: TestReport
}

export interface ComparativeTestResponse {
  model_name: string
  results: Record<string, TestResponse>
}

export interface TestHistoryEntry {
  model_name: string
  timestamp: string
  status: string
  overall_status?: string
  duration?: number
}

export interface ModelWithTest extends ModelInfo {
  running?: boolean
  port?: number | null
  active_requests?: number
  test_status?: string
  test_timestamp?: string
  feature_support?: TestReport['feature_support']
  performance?: TestReport['performance_metrics']
}

export interface SystemCpuStatus {
  percent: number
  cores: number
  cores_physical: number
}

export interface SystemMemoryStatus {
  total_mb: number
  available_mb: number
  used_mb: number
  percent: number
}

export interface SystemDiskStatus {
  total_gb: number
  used_gb: number
  free_gb: number
  percent: number
}

export interface SystemStatus {
  cpu: SystemCpuStatus
  memory: SystemMemoryStatus
  disk: SystemDiskStatus
  timestamp: string
}

export interface QueueModelEntry {
  active_requests: number
  concurrency_limit: number
  can_accept: boolean
}

export interface QueueStatus {
  [modelName: string]: QueueModelEntry
}

export interface HealthAlert {
  should_alert: boolean
  health_score: number
  status: 'healthy' | 'degraded' | 'unhealthy' | 'warning'
  alert_reasons: string[]
  timestamp: string
}

export interface TokenModelStats {
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
}

export interface TokenStats {
  total_prompt_tokens: number
  total_completion_tokens: number
  total_tokens: number
  prompt_tokens?: number
  completion_tokens?: number
  models: Record<string, TokenModelStats>
  timestamp: string
}
