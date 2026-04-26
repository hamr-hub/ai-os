export interface GPUProcess {
  pid: number
  name: string
  used_gpu_memory: number
}

export interface VLLMMetricsData {
  vllm_available: boolean
  running_requests: number
  waiting_requests: number
  gpu_cache_usage: number
  cpu_cache_usage: number
  generation_throughput: number
  prompt_throughput: number
  time_to_first_token: number
  time_per_output_token: number
  prefix_cache_hit_rate: number
  scraped_at: string
}

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
  vllm_metrics?: VLLMMetricsData
  driver_version?: string
  serverTime?: string
}

export interface GPUInfo {
  name: string
  index?: number
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
  ecc_errors?: number
  throttle_reasons?: string[]
  persistence_mode?: boolean
  pcie_rx_throughput?: number
  pcie_tx_throughput?: number
  bar1_total_memory?: number
  bar1_used_memory?: number
  processes?: GPUProcess[]
  vbios_version?: string
  driver_version?: string
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
  clock_sm?: number
  clock_mem?: number
  ecc_errors?: number
  throttle_reasons?: string[]
  vllm_metrics?: VLLMMetricsData
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
  fan_speed?: number
  clock_sm?: number
  clock_mem?: number
  ecc_errors?: number
  vllm_running_requests?: number
  vllm_waiting_requests?: number
  vllm_gpu_cache_usage?: number
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
    description?: string
    required_memory?: string
    backend_type?: string
  }
}

export interface ModelInfo {
  id: string
  object: string
  created: number
  owned_by: string
  name: string
  running: boolean
  port: number | null
  service: string | null
  active_requests: number
  preloaded: boolean
  last_used: string | null
  supports_images?: boolean
  supports_tool_calling?: boolean
  supports_image_generation?: boolean
  description?: string
  required_memory?: string
  backend_type?: string
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
    metrics?: Record<string, unknown>
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
  queue?: QueueStatus
}

export interface SystemHistoryEntry {
  timestamp: string
  cpu_percent: number
  memory_percent: number
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

export interface TokenHistoryEntry {
  timestamp: string
  total_tokens: number
  prompt_tokens: number
  completion_tokens: number
  models?: Record<string, TokenModelStats>
}

export interface TokenStats {
  total_prompt_tokens: number
  total_completion_tokens: number
  total_tokens: number
  prompt_tokens?: number
  completion_tokens?: number
  models: Record<string, TokenModelStats>
  history?: TokenHistoryEntry[]
  timestamp: string
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string | Array<{ type: string; text?: string; image_url?: { url: string } }>
}

export interface ChatCompletionRequest {
  model?: string
  messages: ChatMessage[]
  stream?: boolean
  max_tokens?: number
  temperature?: number
  enable_thinking?: boolean
}

export interface ChatCompletionResponse {
  id: string
  object: string
  created: number
  model: string
  choices: {
    index: number
    message: { role: string; content: string }
    finish_reason: string
  }[]
  usage?: { prompt_tokens: number; completion_tokens: number; total_tokens: number }
}

export interface AgentToolCall {
  name: string
  arguments: Record<string, unknown>
}

export interface AgentMessage {
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string
  tool_calls?: Array<{
    id: string
    type: 'function'
    function: { name: string; arguments: string }
  }>
  tool_call_id?: string
}

export interface AgentRequest {
  model?: string
  messages: AgentMessage[]
  tools?: string[]
  max_iterations?: number
  stream?: boolean
  auto_confirm?: boolean
}

export interface ToolResult {
  tool_name: string
  success: boolean
  result: unknown
  error?: string
  execution_time: number
}

export interface ModelStatusEntry {
  running: boolean
  port: number | null
  service: string | null
  active_requests: number
  preloaded: boolean
  last_used: string | null
  supports_images?: boolean
  supports_tool_calling?: boolean
  supports_image_generation?: boolean
  description?: string
  required_memory?: string
  backend_type?: string
}

export interface GPUEnhancedInfo {
  gpus: Array<{
    index: number
    name: string
    total_memory: number
    used_memory: number
    available_memory: number
    utilization: number
    temperature: number
    power_draw: number
    power_limit: number
    processes: GPUProcess[]
  }>
  driver_version: string
  cuda_version: string
}

export interface TokenHistoryResponse {
  history: Array<{
    timestamp: string
    total_tokens: number
    prompt_tokens: number
    completion_tokens: number
    models: Record<string, TokenModelStats>
  }>
  count: number
}

export interface SystemHistoryResponse {
  history: SystemHistoryEntry[]
  count: number
}
