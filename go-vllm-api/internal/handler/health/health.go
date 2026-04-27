package health

import (
	"net/http"
	"time"

	"go-vllm-api/internal/service"

	prom "go-vllm-api/internal/pkg/prometheus"

	"github.com/gin-gonic/gin"
)

type HealthHandler struct {
	gpuMonitor *service.GPUMonitor
	scheduler  *service.Scheduler
	metrics    *service.MetricsCollector
	cache      *service.CacheService
	prometheus *prom.PrometheusExporter
}

func NewHealthHandler(gpuMonitor *service.GPUMonitor, scheduler *service.Scheduler, metrics *service.MetricsCollector, cache *service.CacheService, prometheus *prom.PrometheusExporter) *HealthHandler {
	return &HealthHandler{
		gpuMonitor: gpuMonitor,
		scheduler:  scheduler,
		metrics:    metrics,
		cache:      cache,
		prometheus: prometheus,
	}
}

func (h *HealthHandler) RegisterRoutes(rg *gin.RouterGroup) {
	rg.GET("/health", h.HealthCheck)
	rg.GET("/health/detailed", h.HealthCheckDetailed)
	rg.GET("/metrics", h.GetPrometheusMetrics)
	rg.GET("/metrics/metadata", h.GetMetricsMetadata)
}

func (h *HealthHandler) HealthCheck(c *gin.Context) {
	refresh := c.Query("refresh") == "true"
	cacheKey := "api:health"

	if !refresh {
		if cached := h.cache.Get(cacheKey); cached != nil {
			c.JSON(http.StatusOK, cached)
			return
		}
	}

	gpuStatus := h.gpuMonitor.GetStatus()
	vllmMetrics := h.gpuMonitor.GetVLLMMetrics()
	healthInfo := h.metrics.GetComprehensiveHealthScore(gpuStatus, vllmMetrics)
	currentModel := h.scheduler.GetCurrentModelName()
	result := gin.H{
		"status":         healthInfo["status"],
		"timestamp":      time.Now().Format(time.RFC3339),
		"health_score":   healthInfo["overall"],
		"current_model":  currentModel,
		"details":        healthInfo,
	}
	h.cache.Set(cacheKey, result, 5)
	c.JSON(http.StatusOK, result)
}

func (h *HealthHandler) HealthCheckDetailed(c *gin.Context) {
	gpuStatus := h.gpuMonitor.GetStatus()
	vllmMetrics := h.gpuMonitor.GetVLLMMetrics()
	healthInfo := h.metrics.GetComprehensiveHealthScore(gpuStatus, vllmMetrics)
	result := gin.H{
		"status":  healthInfo["status"],
		"timestamp": time.Now().Format(time.RFC3339),
		"scores":  healthInfo,
		"gpu":     gpuStatus,
		"metrics": h.metrics.GetDetailedMetrics(),
	}
	c.JSON(http.StatusOK, result)
}

func (h *HealthHandler) GetPrometheusMetrics(c *gin.Context) {
	h.prometheus.Handler().ServeHTTP(c.Writer, c.Request)
}

func (h *HealthHandler) GetMetricsMetadata(c *gin.Context) {
	c.JSON(http.StatusOK, h.prometheus.GetMetricsDict())
}
