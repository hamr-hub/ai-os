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
    path_exists?: boolean
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
  runtime_status?: {
    checked_at: string
    requested_model: string
    backend_type: string
    port: number | null
    service: string | null
    active_requests: number
    requested_model_running: boolean
    service_running: boolean
    active_model?: string | null
    active_model_matches?: boolean
    active_model_path?: string
    default_model?: string | null
  }
  feature_support: {
    chat: boolean
    image: boolean
    tool_calling: boolean
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
  path_exists?: boolean
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

export interface VLLMParams {
  max_num_seqs: number
  gpu_memory_utilization: number
  max_model_len: number
  [key: string]: number | string | boolean | undefined
}

export interface ModelVariant {
  name: string
  path: string
  required_memory_gb: number
  multimodal: boolean
  size_mb: number
  running: boolean
  status: string
  port: number | null
  preloaded: boolean
  active_requests: number
  supports_images: boolean
  supports_tool_calling: boolean
  supports_image_generation: boolean
  description: string
  required_memory: string
  backend_type: string
  vllm_config: VLLMConfig
  is_current: boolean
  path_exists?: boolean
}

export interface ModelGroup {
  base_name: string
  variant_count: number
  total_size_mb: number
  variants: ModelVariant[]
}

export interface AggregatedModelsResponse {
  groups: ModelGroup[]
  total_groups: number
  total_variants: number
  current_model: string | null
}

export interface VLLMConfig {
  gpu_memory_utilization: number | null
  max_model_len: number | null
  max_num_seqs: number | null
  max_num_batched_tokens: number | null
  tensor_parallel_size: number | null
  has_custom_config: boolean
}

export interface VLLMDefaultConfig {
  gpu_memory_utilization: number
  max_model_len: number
  max_num_seqs: number
  max_num_batched_tokens: number
  tensor_parallel_size: number
}

export interface VLLMConfigUpdateRequest {
  gpu_memory_utilization?: number
  max_model_len?: number
  max_num_seqs?: number
  max_num_batched_tokens?: number
  tensor_parallel_size?: number
}

export type SwitchPhaseStatus = 'pending' | 'running' | 'success' | 'failed' | 'skipped'
export type SwitchOverallPhase =
  | 'idle' | 'phase1' | 'phase2' | 'phase3' | 'phase4'
  | 'rolling_back' | 'rolled_back' | 'completed' | 'failed'
export type SwitchLogLevel = 'info' | 'warning' | 'error' | 'success'

export interface SwitchPhaseDetail {
  phase: number
  name: string
  status: SwitchPhaseStatus
  progress: number
  started_at: string | null
  finished_at: string | null
  logs: string[]
  error: string | null
}

export interface SwitchSession {
  session_id: string
  action: 'switch' | 'start' | 'stop'
  target_model: string
  previous_model: string | null
  started_at: string
  finished_at: string | null
  overall_phase: SwitchOverallPhase
  overall_progress: number
  phases: SwitchPhaseDetail[]
  error: string | null
  rollback_reason: string | null
  completed_successfully: boolean
}

export interface SwitchProgressMessage {
  type: 'switch_progress' | 'switch_failed' | 'rollback_started' | 'rollback_completed' | 'switch_state_sync'
  timestamp: string
  session_id: string
  overall_phase: SwitchOverallPhase
  overall_progress: number
  current_phase: number
  phase_progress: number
  log: string
  level: SwitchLogLevel
  target_model: string
  previous_model: string | null
  final: boolean
  session: SwitchSession | null
  is_switching?: boolean
}

export interface SwitchStatusResponse {
  is_switching: boolean
  session: SwitchSession | null
  timestamp: string
}

export type EngineType = 'vllm' | 'sglang' | 'llama_cpp'

export interface EngineStatus {
  vllm: { running: boolean; pid: number | null; port: number | null; model: string | null; uptime: number | null }
  sglang: { running: boolean; pid: number | null; port: number | null; model: string | null; uptime: number | null }
  llama_cpp: { running: boolean; pid: number | null; port: number | null; model: string | null; uptime: number | null }
  current_engine: EngineType
}

export interface EngineConfig {
  vllm: { command: string; default_params: Record<string, unknown> }
  sglang: { command: string; default_params: Record<string, unknown> }
  llama_cpp: { command: string; default_params: Record<string, unknown> }
}

export interface ModelSearchResponse {
  keyword: string
  source: string
  total: number
  models: SearchResult[]
  gpu_info: GPURecommendInfo | null
}

export interface GPUMemoryInfo {
  available: boolean
  total_gb: number
  used_gb: number
  free_gb: number
  safety_available_gb: number
  gpu_name: string
  method: 'torch_cuda' | 'nvidia_smi'
}

export interface DownloadWSMessage {
  event: 'download_started' | 'download_progress' | 'download_completed' | 'download_failed'
  task_id: string
  model_name?: string
  progress_pct?: number
  speed_mbps?: number
  eta_seconds?: number
  downloaded_bytes?: number
  total_bytes?: number
  error_message?: string
  timestamp: string
}

export interface SearchResult {
  name: string
  source: string
  size_b: number | null
  quant: string | null
  required_gb: number | null
  feasible: boolean | null
  model_id: string | null
  description: string | null
}

export interface RecommendResult {
  recommended: SearchResult | null
  gpu_info: GPURecommendInfo
  candidates: SearchResult[]
}

export interface GPURecommendInfo {
  available: boolean
  name?: string
  total_gb?: number
  used_gb?: number
  free_gb?: number
  safety_available_gb?: number
}

export interface DownloadTask {
  task_id: string
  model_name: string
  source: string
  status: 'pending' | 'downloading' | 'completed' | 'failed' | 'cancelled'
  progress_pct: number
  speed_mbps: number
  eta_seconds: number
  downloaded_bytes: number
  total_bytes: number
  local_path: string | null
  error_message: string | null
}

export interface PoolEntry {
  name: string
  source: string
  size_b: number | null
  quant: string | null
  required_gb: number | null
  feasible: boolean | null
  local_path: string | null
  engine_type: string | null
  download_status: 'completed' | 'not_downloaded' | 'downloading' | 'failed'
  running_status: 'running' | 'stopped' | 'loading'
  port: number | null
  config_key: string | null
}

export interface PoolListResponse {
  models: PoolEntry[]
  total: number
  page: number
  page_size: number
}

export interface MemoryCheckResult {
  feasible: boolean
  available_gb: number
  required_gb: number
  safety_margin_gb: number
  gpu_available: boolean
  gpu_name?: string
  free_gb?: number
}

export interface RateLimitConfig {
  ip_qps_limit: number
  ip_qps_window_seconds: number
  concurrency_limit: number
  queue_timeout_seconds: number
  whitelist_ips: string[]
  rate_limited_paths: string[]
}

export interface RateLimitStats {
  total_rejected: number
  recent_429_count: number
  rejection_by_ip: Record<string, number>
  rejection_by_path: Record<string, number>
  current_queue_depth: number
  timestamp: string
}

export interface SystemConfig {
  health_check_interval_seconds: number
  cache_ttl_seconds: number
  log_level: string
  gpu_poll_interval_seconds: number
  ws_push_interval_seconds: number
}

export interface HealthDetail {
  overall_score: number
  status: 'healthy' | 'degraded' | 'unhealthy'
  checks: {
    gpu: { available: boolean; utilization: number; temperature: number; memory_used_pct: number }
    go_backend: { reachable: boolean; response_time_ms: number }
    python_backend: { reachable: boolean; response_time_ms: number }
    vllm_service: { running: boolean; active_requests: number }
    redis: { available: boolean; connected: boolean }
  }
  alert_reasons: string[]
  timestamp: string
}

export interface HealthHistoryEntry {
  timestamp: string
  health_score: number
  status: string
  alert_count: number
}
