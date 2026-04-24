package prometheus

import (
	"net/http"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

type PrometheusExporter struct {
	registry        *prometheus.Registry
	requestCounter  *prometheus.CounterVec
	requestDuration *prometheus.HistogramVec
	activeRequests  *prometheus.GaugeVec
	gpuMemory       *prometheus.GaugeVec
	gpuTemperature  *prometheus.GaugeVec
	gpuUtilization  *prometheus.GaugeVec
	gpuPowerDraw    *prometheus.GaugeVec
	gpuFanSpeed     *prometheus.GaugeVec
	gpuClockSM      *prometheus.GaugeVec
	gpuEccErrors    *prometheus.GaugeVec
	gpuPCIeThroughput *prometheus.GaugeVec
	gpuBar1Memory   *prometheus.GaugeVec
	gpuThrottleStatus *prometheus.GaugeVec
	modelStatus     *prometheus.GaugeVec
	queueLength     *prometheus.GaugeVec
	uptime          prometheus.Gauge
	healthScore     prometheus.Gauge

	vllmRunningRequests     prometheus.Gauge
	vllmWaitingRequests     prometheus.Gauge
	vllmGPUCacheUsage       prometheus.Gauge
	vllmCPUCacheUsage       prometheus.Gauge
	vllmGenerationThroughput prometheus.Gauge
	vllmPromptThroughput    prometheus.Gauge
	vllmTTFT                prometheus.Gauge
	vllmTPOT                prometheus.Gauge
	vllmPrefixCacheHitRate  prometheus.Gauge
}

func NewPrometheusExporter() *PrometheusExporter {
	reg := prometheus.NewRegistry()

	pe := &PrometheusExporter{registry: reg}

	pe.requestCounter = prometheus.NewCounterVec(
		prometheus.CounterOpts{Name: "vllm_api_requests_total", Help: "Total API requests"},
		[]string{"endpoint", "method", "status"},
	)
	pe.requestDuration = prometheus.NewHistogramVec(
		prometheus.HistogramOpts{Name: "vllm_api_request_duration_seconds", Help: "Request duration", Buckets: prometheus.DefBuckets},
		[]string{"endpoint"},
	)
	pe.activeRequests = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{Name: "vllm_api_active_requests", Help: "Active requests per model"},
		[]string{"model"},
	)
	pe.gpuMemory = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{Name: "vllm_api_gpu_memory_bytes", Help: "GPU memory usage"},
		[]string{"type", "gpu_id"},
	)
	pe.gpuTemperature = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{Name: "vllm_api_gpu_temperature_celsius", Help: "GPU temperature"},
		[]string{"gpu_id"},
	)
	pe.gpuUtilization = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{Name: "vllm_api_gpu_utilization_percent", Help: "GPU utilization"},
		[]string{"gpu_id"},
	)
	pe.gpuPowerDraw = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{Name: "vllm_api_gpu_power_draw_watts", Help: "GPU power draw in watts"},
		[]string{"gpu_id"},
	)
	pe.gpuFanSpeed = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{Name: "vllm_api_gpu_fan_speed_percent", Help: "GPU fan speed"},
		[]string{"gpu_id"},
	)
	pe.gpuClockSM = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{Name: "vllm_api_gpu_clock_sm_mhz", Help: "GPU SM clock in MHz"},
		[]string{"gpu_id"},
	)
	pe.gpuEccErrors = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{Name: "vllm_api_gpu_ecc_errors_total", Help: "GPU ECC errors"},
		[]string{"gpu_id"},
	)
	pe.gpuPCIeThroughput = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{Name: "vllm_api_gpu_pcie_throughput_kbps", Help: "GPU PCIe throughput"},
		[]string{"gpu_id", "direction"},
	)
	pe.gpuBar1Memory = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{Name: "vllm_api_gpu_bar1_memory_bytes", Help: "GPU BAR1 memory"},
		[]string{"gpu_id", "type"},
	)
	pe.gpuThrottleStatus = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{Name: "vllm_api_gpu_throttle_status", Help: "GPU throttle status (1=throttled)"},
		[]string{"gpu_id"},
	)
	pe.modelStatus = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{Name: "vllm_api_model_status", Help: "Model running status"},
		[]string{"model", "service"},
	)
	pe.queueLength = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{Name: "vllm_api_queue_length", Help: "Queue length per model"},
		[]string{"model"},
	)
	pe.uptime = prometheus.NewGauge(prometheus.GaugeOpts{Name: "vllm_api_uptime_seconds", Help: "Service uptime"})
	pe.healthScore = prometheus.NewGauge(prometheus.GaugeOpts{Name: "vllm_api_health_score", Help: "Overall health score"})

	pe.vllmRunningRequests = prometheus.NewGauge(prometheus.GaugeOpts{Name: "vllm_api_vllm_running_requests", Help: "vLLM running requests"})
	pe.vllmWaitingRequests = prometheus.NewGauge(prometheus.GaugeOpts{Name: "vllm_api_vllm_waiting_requests", Help: "vLLM waiting requests"})
	pe.vllmGPUCacheUsage = prometheus.NewGauge(prometheus.GaugeOpts{Name: "vllm_api_vllm_gpu_cache_usage_percent", Help: "vLLM GPU KV cache usage"})
	pe.vllmCPUCacheUsage = prometheus.NewGauge(prometheus.GaugeOpts{Name: "vllm_api_vllm_cpu_cache_usage_percent", Help: "vLLM CPU KV cache usage"})
	pe.vllmGenerationThroughput = prometheus.NewGauge(prometheus.GaugeOpts{Name: "vllm_api_vllm_generation_throughput", Help: "vLLM generation throughput tokens/s"})
	pe.vllmPromptThroughput = prometheus.NewGauge(prometheus.GaugeOpts{Name: "vllm_api_vllm_prompt_throughput", Help: "vLLM prompt throughput tokens/s"})
	pe.vllmTTFT = prometheus.NewGauge(prometheus.GaugeOpts{Name: "vllm_api_vllm_ttft_seconds", Help: "vLLM time to first token"})
	pe.vllmTPOT = prometheus.NewGauge(prometheus.GaugeOpts{Name: "vllm_api_vllm_tpot_seconds", Help: "vLLM time per output token"})
	pe.vllmPrefixCacheHitRate = prometheus.NewGauge(prometheus.GaugeOpts{Name: "vllm_api_vllm_prefix_cache_hit_rate_percent", Help: "vLLM prefix cache hit rate"})

	reg.MustRegister(
		pe.requestCounter, pe.requestDuration, pe.activeRequests,
		pe.gpuMemory, pe.gpuTemperature, pe.gpuUtilization,
		pe.gpuPowerDraw, pe.gpuFanSpeed, pe.gpuClockSM,
		pe.gpuEccErrors, pe.gpuPCIeThroughput, pe.gpuBar1Memory,
		pe.gpuThrottleStatus,
		pe.modelStatus, pe.queueLength, pe.uptime, pe.healthScore,
		pe.vllmRunningRequests, pe.vllmWaitingRequests,
		pe.vllmGPUCacheUsage, pe.vllmCPUCacheUsage,
		pe.vllmGenerationThroughput, pe.vllmPromptThroughput,
		pe.vllmTTFT, pe.vllmTPOT, pe.vllmPrefixCacheHitRate,
	)

	return pe
}

func (pe *PrometheusExporter) RecordRequest(endpoint, method string, status int, duration float64) {
	pe.requestCounter.WithLabelValues(endpoint, method, statusLabel(status)).Inc()
	pe.requestDuration.WithLabelValues(endpoint).Observe(duration)
}

func statusLabel(code int) string {
	if code < 200 {
		return "1xx"
	} else if code < 300 {
		return "2xx"
	} else if code < 400 {
		return "3xx"
	} else if code < 500 {
		return "4xx"
	}
	return "5xx"
}

func (pe *PrometheusExporter) SetModelStatus(model, service string, running bool) {
	val := 0.0
	if running {
		val = 1.0
	}
	pe.modelStatus.WithLabelValues(model, service).Set(val)
}

func (pe *PrometheusExporter) SetActiveRequests(model string, count int) {
	pe.activeRequests.WithLabelValues(model).Set(float64(count))
}

func (pe *PrometheusExporter) SetHealthScore(score float64) {
	pe.healthScore.Set(score)
}

type GPUMetricsData struct {
	GPUCount        int
	GPUs            []GPUGPUMetricEntry
}

type GPUGPUMetricEntry struct {
	ID             string
	TotalMemory    int64
	UsedMemory     int64
	AvailableMemory int64
	Temperature    int
	Utilization    int
	PowerDraw      int
	FanSpeed       int
	ClockSM        int
	EccErrors      int
	PCIeRx         int
	PCIeTx         int
	Bar1Total      int64
	Bar1Used       int64
	Throttled      bool
}

func (pe *PrometheusExporter) UpdateGPUMetrics(data *GPUMetricsData) {
	if data == nil {
		return
	}
	for _, gpu := range data.GPUs {
		pe.gpuMemory.WithLabelValues("total", gpu.ID).Set(float64(gpu.TotalMemory))
		pe.gpuMemory.WithLabelValues("used", gpu.ID).Set(float64(gpu.UsedMemory))
		pe.gpuMemory.WithLabelValues("available", gpu.ID).Set(float64(gpu.AvailableMemory))
		pe.gpuTemperature.WithLabelValues(gpu.ID).Set(float64(gpu.Temperature))
		pe.gpuUtilization.WithLabelValues(gpu.ID).Set(float64(gpu.Utilization))
		pe.gpuPowerDraw.WithLabelValues(gpu.ID).Set(float64(gpu.PowerDraw))
		pe.gpuFanSpeed.WithLabelValues(gpu.ID).Set(float64(gpu.FanSpeed))
		pe.gpuClockSM.WithLabelValues(gpu.ID).Set(float64(gpu.ClockSM))
		pe.gpuEccErrors.WithLabelValues(gpu.ID).Set(float64(gpu.EccErrors))
		pe.gpuPCIeThroughput.WithLabelValues(gpu.ID, "rx").Set(float64(gpu.PCIeRx))
		pe.gpuPCIeThroughput.WithLabelValues(gpu.ID, "tx").Set(float64(gpu.PCIeTx))
		pe.gpuBar1Memory.WithLabelValues(gpu.ID, "total").Set(float64(gpu.Bar1Total))
		pe.gpuBar1Memory.WithLabelValues(gpu.ID, "used").Set(float64(gpu.Bar1Used))
		throttleVal := 0.0
		if gpu.Throttled {
			throttleVal = 1.0
		}
		pe.gpuThrottleStatus.WithLabelValues(gpu.ID).Set(throttleVal)
	}
}

type VLLMMetricsData struct {
	RunningRequests      float64
	WaitingRequests      float64
	GPUCacheUsage        float64
	CPUCacheUsage        float64
	GenerationThroughput float64
	PromptThroughput     float64
	TTFT                 float64
	TPOT                 float64
	PrefixCacheHitRate   float64
}

func (pe *PrometheusExporter) UpdateVLLMMetrics(data *VLLMMetricsData) {
	if data == nil {
		return
	}
	pe.vllmRunningRequests.Set(data.RunningRequests)
	pe.vllmWaitingRequests.Set(data.WaitingRequests)
	pe.vllmGPUCacheUsage.Set(data.GPUCacheUsage)
	pe.vllmCPUCacheUsage.Set(data.CPUCacheUsage)
	pe.vllmGenerationThroughput.Set(data.GenerationThroughput)
	pe.vllmPromptThroughput.Set(data.PromptThroughput)
	pe.vllmTTFT.Set(data.TTFT)
	pe.vllmTPOT.Set(data.TPOT)
	pe.vllmPrefixCacheHitRate.Set(data.PrefixCacheHitRate)
}

func (pe *PrometheusExporter) Handler() http.Handler {
	return promhttp.HandlerFor(pe.registry, promhttp.HandlerOpts{})
}

func (pe *PrometheusExporter) GetMetricsDict() map[string]string {
	return map[string]string{
		"requests_total":           "vllm_api_requests_total",
		"request_duration":         "vllm_api_request_duration_seconds",
		"active_requests":          "vllm_api_active_requests",
		"gpu_memory":               "vllm_api_gpu_memory_bytes",
		"gpu_temperature":          "vllm_api_gpu_temperature_celsius",
		"gpu_utilization":          "vllm_api_gpu_utilization_percent",
		"gpu_power_draw":           "vllm_api_gpu_power_draw_watts",
		"gpu_fan_speed":            "vllm_api_gpu_fan_speed_percent",
		"gpu_clock_sm":             "vllm_api_gpu_clock_sm_mhz",
		"gpu_ecc_errors":           "vllm_api_gpu_ecc_errors_total",
		"gpu_pcie_throughput":      "vllm_api_gpu_pcie_throughput_kbps",
		"gpu_bar1_memory":          "vllm_api_gpu_bar1_memory_bytes",
		"gpu_throttle_status":      "vllm_api_gpu_throttle_status",
		"model_status":             "vllm_api_model_status",
		"queue_length":             "vllm_api_queue_length",
		"uptime":                   "vllm_api_uptime_seconds",
		"health_score":             "vllm_api_health_score",
		"vllm_running_requests":    "vllm_api_vllm_running_requests",
		"vllm_waiting_requests":    "vllm_api_vllm_waiting_requests",
		"vllm_gpu_cache_usage":     "vllm_api_vllm_gpu_cache_usage_percent",
		"vllm_cpu_cache_usage":     "vllm_api_vllm_cpu_cache_usage_percent",
		"vllm_generation_throughput": "vllm_api_vllm_generation_throughput",
		"vllm_prompt_throughput":   "vllm_api_vllm_prompt_throughput",
		"vllm_ttft":                "vllm_api_vllm_ttft_seconds",
		"vllm_tpot":                "vllm_api_vllm_tpot_seconds",
		"vllm_prefix_cache_hit_rate": "vllm_api_vllm_prefix_cache_hit_rate_percent",
	}
}
