package health

import (
	"net/http"
	"time"

	"go-vllm-api/internal/repository"
	"go-vllm-api/internal/service"

	prom "go-vllm-api/internal/pkg/prometheus"

	"github.com/gin-gonic/gin"
)

type VLLMProxyAccessor interface {
	CircuitBreakerStats() map[string]interface{}
}

type SysCtlAccessor interface {
	IsServiceRunning(name string) bool
	GetServiceInfo(name string) map[string]string
}

type LlamaCppAccessor interface {
	GetServerStatus() map[string]service.LlamaCppProcessInfo
	IsServerRunning(modelName string) bool
}

type HealthHandler struct {
	gpuMonitor  *service.GPUMonitor
	scheduler   *service.Scheduler
	metrics     *service.MetricsCollector
	cache       *service.CacheService
	prometheus  *prom.PrometheusExporter
	vllmProxy   VLLMProxyAccessor
	sysCtl      SysCtlAccessor
	llamaCppMgr LlamaCppAccessor
	redisRepo   *repository.RedisRepo
}

func NewHealthHandler(gpuMonitor *service.GPUMonitor, scheduler *service.Scheduler, metrics *service.MetricsCollector, cache *service.CacheService, prometheus *prom.PrometheusExporter, vllmProxy VLLMProxyAccessor, sysCtl SysCtlAccessor, llamaCppMgr LlamaCppAccessor, redisRepo *repository.RedisRepo) *HealthHandler {
	return &HealthHandler{
		gpuMonitor:  gpuMonitor,
		scheduler:   scheduler,
		metrics:     metrics,
		cache:       cache,
		prometheus:  prometheus,
		vllmProxy:   vllmProxy,
		sysCtl:      sysCtl,
		llamaCppMgr: llamaCppMgr,
		redisRepo:   redisRepo,
	}
}

func (h *HealthHandler) RegisterRoutes(rg *gin.RouterGroup) {
	rg.GET("/health", h.HealthCheck)
	rg.GET("/health/detailed", h.HealthCheckDetailed)
	rg.GET("/metrics", h.GetPrometheusMetrics)
	rg.GET("/metrics/metadata", h.GetMetricsMetadata)
}

func (h *HealthHandler) buildEngineStatus() map[string]interface{} {
	engines := map[string]interface{}{}
	vllmRunning := h.sysCtl.IsServiceRunning("vllm-aiclient")
	vllmInfo := h.sysCtl.GetServiceInfo("vllm-aiclient")
	engines["vllm"] = map[string]interface{}{
		"running": vllmRunning,
		"status":  vllmInfo["status"],
		"port":    vllmInfo["port"],
	}
	llamaStatus := h.llamaCppMgr.GetServerStatus()
	llamaMap := map[string]interface{}{}
	for k, v := range llamaStatus {
		llamaMap[k] = v
	}
	engines["llama_cpp"] = llamaMap
	return engines
}

func (h *HealthHandler) buildModelStatus() map[string]interface{} {
	models := h.scheduler.GetAvailableModels()
	modelStatus := map[string]interface{}{}
	for _, m := range models {
		modelStatus[m] = map[string]interface{}{
			"running":         h.scheduler.IsModelRunning(m),
			"port":            h.scheduler.GetModelPort(m),
			"service":         h.scheduler.GetModelService(m),
			"active_requests": h.scheduler.GetActiveRequests(m),
			"preloaded":       h.scheduler.IsModelPreloaded(m),
			"backend_type":    h.scheduler.GetModelBackendType(m),
		}
	}
	return modelStatus
}

func (h *HealthHandler) buildQueueStatus() map[string]interface{} {
	models := h.scheduler.GetAvailableModels()
	queue := map[string]interface{}{}
	for _, m := range models {
		queue[m] = map[string]interface{}{
			"active_requests":   h.scheduler.GetActiveRequests(m),
			"concurrency_limit": h.scheduler.GetConcurrencyLimit(),
			"can_accept":        h.scheduler.CanAcceptRequest(m),
		}
	}
	return queue
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
		"status":          healthInfo["status"],
		"timestamp":       time.Now().Format(time.RFC3339),
		"health_score":    healthInfo["overall"],
		"current_model":   currentModel,
		"default_model":   h.scheduler.GetDefaultModel(),
		"switching":       h.scheduler.IsSwitchingInProgress(),
		"details":         healthInfo,
		"engines":         h.buildEngineStatus(),
		"models":          h.buildModelStatus(),
		"circuit_breaker": h.vllmProxy.CircuitBreakerStats(),
		"redis":           h.redisRepo.IsConnected(),
	}

	h.cache.Set(cacheKey, result, 5)
	c.JSON(http.StatusOK, result)
}

func (h *HealthHandler) HealthCheckDetailed(c *gin.Context) {
	gpuStatus := h.gpuMonitor.GetStatus()
	vllmMetrics := h.gpuMonitor.GetVLLMMetrics()
	healthInfo := h.metrics.GetComprehensiveHealthScore(gpuStatus, vllmMetrics)

	result := gin.H{
		"status":          healthInfo["status"],
		"timestamp":       time.Now().Format(time.RFC3339),
		"scores":          healthInfo,
		"gpu":             gpuStatus,
		"gpu_summary":     h.gpuMonitor.GetGPUSummary(),
		"gpu_processes":   h.gpuMonitor.GetGPUProcesses(),
		"engines":         h.buildEngineStatus(),
		"models":          h.buildModelStatus(),
		"metrics":         h.metrics.GetDetailedMetrics(),
		"circuit_breaker": h.vllmProxy.CircuitBreakerStats(),
		"redis":           h.redisRepo.IsConnected(),
		"redis_stats":     h.redisRepo.GetStats(),
		"queue":           h.buildQueueStatus(),
	}

	c.JSON(http.StatusOK, result)
}

func (h *HealthHandler) GetPrometheusMetrics(c *gin.Context) {
	h.prometheus.Handler().ServeHTTP(c.Writer, c.Request)
}

func (h *HealthHandler) GetMetricsMetadata(c *gin.Context) {
	c.JSON(http.StatusOK, h.prometheus.GetMetricsDict())
}
