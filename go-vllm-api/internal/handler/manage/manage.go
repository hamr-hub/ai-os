package manage

import (
	"fmt"
	"net/http"
	"time"

	"go-vllm-api/internal/service"

	"github.com/gin-gonic/gin"
)

type ManageHandler struct {
	scheduler   *service.Scheduler
	gpuMonitor  *service.GPUMonitor
	sysCtl      *service.SystemController
	metrics     *service.MetricsCollector
	cache       *service.CacheService
	cacheUpdater *service.CacheUpdater
	wsManager   *service.WSManager
}

func NewManageHandler(scheduler *service.Scheduler, gpuMonitor *service.GPUMonitor, sysCtl *service.SystemController, metrics *service.MetricsCollector, cache *service.CacheService, cacheUpdater *service.CacheUpdater, wsManager *service.WSManager) *ManageHandler {
	return &ManageHandler{
		scheduler:    scheduler,
		gpuMonitor:   gpuMonitor,
		sysCtl:       sysCtl,
		metrics:      metrics,
		cache:        cache,
		cacheUpdater: cacheUpdater,
		wsManager:    wsManager,
	}
}

func (h *ManageHandler) RegisterRoutes(rg *gin.RouterGroup) {
	m := rg.Group("/manage")
	{
		m.GET("/gpu", h.GetGPUStatus)
		m.GET("/gpu/summary", h.GetGPUSummary)
		m.GET("/models", h.GetModelStatus)
		m.GET("/models/summary", h.ModelsSummary)
		m.POST("/models/:model_name/start", h.StartModel)
		m.POST("/models/:model_name/stop", h.StopModel)
		m.POST("/models/:model_name/switch", h.SwitchModel)
		m.GET("/default-model", h.GetDefaultModel)
		m.POST("/default-model/:model_name", h.SetDefaultModel)
		m.DELETE("/default-model", h.ClearDefaultModel)
		m.GET("/queue", h.GetQueueStatus)
		m.GET("/preload", h.GetPreload)
		m.POST("/preload/:model_name", h.PreloadModel)
		m.GET("/metrics", h.GetMetrics)
		m.POST("/metrics/reset", h.ResetMetrics)
		m.GET("/health/alert", h.CheckAlertStatus)
		m.GET("/cache/status", h.GetCacheStatus)
		m.POST("/cache/refresh", h.RefreshCache)
		m.GET("/cache/stats", h.GetCacheStats)
		m.GET("/config", h.GetConfig)
		m.POST("/config/reload", h.ReloadConfig)
		m.GET("/system/status", h.SystemStatus)
		m.GET("/websocket/connections", h.GetWebSocketConnections)
	}

	api := rg.Group("/api/v1")
	{
		api.GET("/status", h.NodeIntegrationStatus)
		api.GET("/models/:model_name/info", h.ModelInfo)
	}
}

func (h *ManageHandler) GetGPUStatus(c *gin.Context) {
	refresh := c.Query("refresh") == "true"
	cacheKey := "api:manage:gpu:status"

	if !refresh {
		if cached := h.cache.Get(cacheKey); cached != nil {
			c.JSON(http.StatusOK, cached)
			return
		}
	}

	status := h.gpuMonitor.GetStatus()
	var result interface{}
	if status == nil {
		result = gin.H{"status": "unavailable", "message": "No GPU detected", "serverTime": time.Now().Format(time.RFC3339)}
	} else {
		status.ServerTime = time.Now().Format(time.RFC3339)
		result = status
	}
	h.cache.Set(cacheKey, result, 10)
	c.JSON(http.StatusOK, result)
}

func (h *ManageHandler) GetGPUSummary(c *gin.Context) {
	status := h.gpuMonitor.GetStatus()
	summary := gin.H{"status": "unavailable"}
	if status != nil {
		summary = gin.H{
			"status":    "available",
			"name":      status.Name,
			"used":      status.UsedMemory,
			"available": status.AvailableMemory,
			"total":     status.TotalMemory,
		}
	}
	c.JSON(http.StatusOK, summary)
}

func (h *ManageHandler) GetModelStatus(c *gin.Context) {
	models := h.scheduler.GetAvailableModels()
	status := make(map[string]interface{})
	for _, m := range models {
		status[m] = gin.H{
			"running":         h.scheduler.IsModelRunning(m),
			"port":            h.scheduler.GetModelPort(m),
			"service":         h.scheduler.GetModelService(m),
			"active_requests": h.scheduler.GetActiveRequests(m),
			"preloaded":       h.scheduler.IsModelPreloaded(m),
		}
	}
	c.JSON(http.StatusOK, status)
}

func (h *ManageHandler) ModelsSummary(c *gin.Context) {
	models := h.scheduler.GetAvailableModels()
	summary := make([]map[string]interface{}, 0)
	for _, m := range models {
		mc := h.scheduler.GetModelConfig(m)
		entry := gin.H{
			"name":     m,
			"running":  h.scheduler.IsModelRunning(m),
			"preloaded": h.scheduler.IsModelPreloaded(m),
			"port":     h.scheduler.GetModelPort(m),
		}
		if mc != nil {
			entry["supports_images"] = mc.SupportsImages
			entry["description"] = mc.Description
			entry["required_memory"] = mc.RequiredMemory
		}
		summary = append(summary, entry)
	}
	c.JSON(http.StatusOK, gin.H{
		"models":        summary,
		"total":         len(summary),
		"running_model": h.scheduler.GetCurrentModelName(),
	})
}

func (h *ManageHandler) StartModel(c *gin.Context) {
	modelName := c.Param("model_name")
	if !h.scheduler.IsModelAvailable(modelName) {
		c.JSON(http.StatusNotFound, gin.H{"error": fmt.Sprintf("Model not found: %s", modelName)})
		return
	}
	if h.scheduler.IsModelRunning(modelName) {
		c.JSON(http.StatusOK, gin.H{"status": "already_running", "model": modelName})
		return
	}
	ok, err := h.scheduler.StartModel(c.Request.Context(), modelName)
	if ok {
		c.JSON(http.StatusOK, gin.H{"status": "starting", "model": modelName})
	} else {
		c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("Failed to start model %s: %v", modelName, err)})
	}
}

func (h *ManageHandler) StopModel(c *gin.Context) {
	modelName := c.Param("model_name")
	if !h.scheduler.IsModelAvailable(modelName) {
		c.JSON(http.StatusNotFound, gin.H{"error": fmt.Sprintf("Model not found: %s", modelName)})
		return
	}
	if !h.scheduler.IsModelRunning(modelName) {
		c.JSON(http.StatusOK, gin.H{"status": "already_stopped", "model": modelName})
		return
	}
	ok := h.scheduler.StopModel(c.Request.Context(), modelName)
	if ok {
		c.JSON(http.StatusOK, gin.H{"status": "stopped", "model": modelName})
	} else {
		c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("Failed to stop model %s", modelName)})
	}
}

func (h *ManageHandler) SwitchModel(c *gin.Context) {
	modelName := c.Param("model_name")
	if !h.scheduler.IsModelAvailable(modelName) {
		c.JSON(http.StatusNotFound, gin.H{"error": fmt.Sprintf("Model not found: %s", modelName)})
		return
	}
	ok := h.scheduler.SwitchModel(c.Request.Context(), modelName)
	if !ok {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": fmt.Sprintf("Failed to switch to model %s, insufficient memory", modelName)})
		return
	}
	h.scheduler.MarkModelSelected(modelName)
	c.JSON(http.StatusOK, gin.H{"status": "switched", "model": modelName})
}

func (h *ManageHandler) GetDefaultModel(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{"default_model": h.scheduler.GetDefaultModel()})
}

func (h *ManageHandler) SetDefaultModel(c *gin.Context) {
	modelName := c.Param("model_name")
	if !h.scheduler.IsModelAvailable(modelName) {
		c.JSON(http.StatusNotFound, gin.H{"error": fmt.Sprintf("Model not found: %s", modelName)})
		return
	}
	h.scheduler.SetDefaultModel(modelName)
	c.JSON(http.StatusOK, gin.H{"status": "success", "default_model": modelName})
}

func (h *ManageHandler) ClearDefaultModel(c *gin.Context) {
	h.scheduler.ClearDefaultModel()
	c.JSON(http.StatusOK, gin.H{"status": "success", "message": "Default model cleared"})
}

func (h *ManageHandler) GetQueueStatus(c *gin.Context) {
	models := h.scheduler.GetAvailableModels()
	info := make(map[string]interface{})
	for _, m := range models {
		info[m] = gin.H{
			"active_requests":    h.scheduler.GetActiveRequests(m),
			"concurrency_limit": h.scheduler.GetConcurrencyLimit(),
			"can_accept":         h.scheduler.CanAcceptRequest(m),
		}
	}
	c.JSON(http.StatusOK, info)
}

func (h *ManageHandler) GetPreload(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"preloaded_models": h.scheduler.GetPreloadedModels(),
		"all_models":       h.scheduler.GetAvailableModels(),
	})
}

func (h *ManageHandler) PreloadModel(c *gin.Context) {
	modelName := c.Param("model_name")
	if !h.scheduler.IsModelAvailable(modelName) {
		c.JSON(http.StatusNotFound, gin.H{"error": fmt.Sprintf("Model not found: %s", modelName)})
		return
	}
	ok, _ := h.scheduler.StartModel(c.Request.Context(), modelName)
	if ok {
		c.JSON(http.StatusOK, gin.H{"status": "preloaded", "model": modelName})
	} else {
		c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("Failed to preload model %s", modelName)})
	}
}

func (h *ManageHandler) GetMetrics(c *gin.Context) {
	c.JSON(http.StatusOK, h.metrics.GetMetrics())
}

func (h *ManageHandler) ResetMetrics(c *gin.Context) {
	h.metrics.Reset()
	h.cache.Delete("api:manage:metrics")
	c.JSON(http.StatusOK, gin.H{"status": "reset"})
}

func (h *ManageHandler) CheckAlertStatus(c *gin.Context) {
	gpuStatus := h.gpuMonitor.GetStatus()
	healthInfo := h.metrics.GetComprehensiveHealthScore(gpuStatus)
	overallScore := 0.0
	if v, ok := healthInfo["overall"].(float64); ok {
		overallScore = v
	}
	c.JSON(http.StatusOK, gin.H{
		"should_alert": overallScore < 70,
		"health_score": overallScore,
		"status":       healthInfo["status"],
		"timestamp":     time.Now().Format(time.RFC3339),
	})
}

func (h *ManageHandler) GetCacheStatus(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"cache_updater": h.cacheUpdater.GetStatus(),
		"cache_service": h.cache.GetStats(),
		"timestamp":     time.Now().Format(time.RFC3339),
	})
}

func (h *ManageHandler) RefreshCache(c *gin.Context) {
	endpoint := c.Query("endpoint")
	if endpoint == "" {
		h.cache.FlushAll()
		c.JSON(http.StatusOK, gin.H{"status": "all_refreshed"})
		return
	}
	c.JSON(http.StatusOK, gin.H{"status": "refreshed", "endpoint": endpoint})
}

func (h *ManageHandler) GetCacheStats(c *gin.Context) {
	c.JSON(http.StatusOK, h.cache.GetStats())
}

func (h *ManageHandler) GetConfig(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{"status": "config endpoint - use POST /manage/config/reload to reload"})
}

func (h *ManageHandler) ReloadConfig(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{"status": "reloaded"})
}

func (h *ManageHandler) SystemStatus(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{"timestamp": time.Now().Format(time.RFC3339)})
}

func (h *ManageHandler) GetWebSocketConnections(c *gin.Context) {
	c.JSON(http.StatusOK, h.wsManager.GetConnectionStats())
}

func (h *ManageHandler) NodeIntegrationStatus(c *gin.Context) {
	gpuStatus := h.gpuMonitor.GetStatus()
	models := h.scheduler.GetAvailableModels()
	modelStatuses := make(map[string]interface{})
	for _, m := range models {
		modelStatuses[m] = gin.H{
			"available":       h.scheduler.IsModelAvailable(m),
			"running":         h.scheduler.IsModelRunning(m),
			"preloaded":       h.scheduler.IsModelPreloaded(m),
			"port":            h.scheduler.GetModelPort(m),
			"supports_images":  h.scheduler.GetModelSupportsImages(m),
			"active_requests":  h.scheduler.GetActiveRequests(m),
			"can_accept":       h.scheduler.CanAcceptRequest(m),
		}
	}

	result := gin.H{
		"service":  "ai-controller",
		"status":   func() string { if gpuStatus != nil { return "healthy" }; return "degraded" }(),
		"timestamp": time.Now().Format(time.RFC3339),
		"models":   modelStatuses,
		"queue": gin.H{
			"concurrency_limit": h.scheduler.GetConcurrencyLimit(),
		},
	}
	c.JSON(http.StatusOK, result)
}

func (h *ManageHandler) ModelInfo(c *gin.Context) {
	modelName := c.Param("model_name")
	if !h.scheduler.IsModelAvailable(modelName) {
		c.JSON(http.StatusNotFound, gin.H{"error": fmt.Sprintf("Model not found: %s", modelName)})
		return
	}
	mc := h.scheduler.GetModelConfig(modelName)
	info := gin.H{
		"name":             modelName,
		"available":        true,
		"running":          h.scheduler.IsModelRunning(modelName),
		"preloaded":        h.scheduler.IsModelPreloaded(modelName),
		"port":             h.scheduler.GetModelPort(modelName),
		"model_path":       h.scheduler.GetModelPath(modelName),
		"service":          h.scheduler.GetModelService(modelName),
		"supports_images":  h.scheduler.GetModelSupportsImages(modelName),
		"active_requests":  h.scheduler.GetActiveRequests(modelName),
		"can_accept":       h.scheduler.CanAcceptRequest(modelName),
	}
	if mc != nil {
		info["description"] = mc.Description
		info["required_memory"] = mc.RequiredMemory
	}
	c.JSON(http.StatusOK, info)
}
