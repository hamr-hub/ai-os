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
	modelStatus     *prometheus.GaugeVec
	queueLength     *prometheus.GaugeVec
	uptime          prometheus.Gauge
	healthScore     prometheus.Gauge
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
		[]string{"type"},
	)
	pe.gpuTemperature = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{Name: "vllm_api_gpu_temperature_celsius", Help: "GPU temperature"},
		[]string{},
	)
	pe.gpuUtilization = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{Name: "vllm_api_gpu_utilization_percent", Help: "GPU utilization"},
		[]string{},
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

	reg.MustRegister(
		pe.requestCounter, pe.requestDuration, pe.activeRequests,
		pe.gpuMemory, pe.gpuTemperature, pe.gpuUtilization,
		pe.modelStatus, pe.queueLength, pe.uptime, pe.healthScore,
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

func (pe *PrometheusExporter) Handler() http.Handler {
	return promhttp.HandlerFor(pe.registry, promhttp.HandlerOpts{})
}

func (pe *PrometheusExporter) GetMetricsDict() map[string]string {
	return map[string]string{
		"requests_total":   "vllm_api_requests_total",
		"request_duration": "vllm_api_request_duration_seconds",
		"active_requests":  "vllm_api_active_requests",
		"gpu_memory":       "vllm_api_gpu_memory_bytes",
		"gpu_temperature":  "vllm_api_gpu_temperature_celsius",
		"gpu_utilization":  "vllm_api_gpu_utilization_percent",
		"model_status":     "vllm_api_model_status",
		"queue_length":     "vllm_api_queue_length",
		"uptime":           "vllm_api_uptime_seconds",
		"health_score":     "vllm_api_health_score",
	}
}
