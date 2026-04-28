package manage

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"go-vllm-api/internal/config"
	"go-vllm-api/internal/repository"
	"go-vllm-api/internal/service"

	"github.com/gin-gonic/gin"
)

type ManageHandler struct {
	scheduler    *service.Scheduler
	gpuMonitor   *service.GPUMonitor
	sysCtl       *service.SystemController
	sysCollector *service.SystemStatusCollector
	metrics      *service.MetricsCollector
	cache        *service.CacheService
	cacheUpdater *service.CacheUpdater
	wsManager    *service.WSManager
	vllmManager  *service.VLLMManager
	llamaCppMgr  *service.LlamaCppManager
	modelTesting *service.ModelTestingFramework
	redis        *repository.RedisRepo
	configPath   string
}

func NewManageHandler(
	scheduler *service.Scheduler,
	gpuMonitor *service.GPUMonitor,
	sysCtl *service.SystemController,
	sysCollector *service.SystemStatusCollector,
	metrics *service.MetricsCollector,
	cache *service.CacheService,
	cacheUpdater *service.CacheUpdater,
	wsManager *service.WSManager,
	vllmManager *service.VLLMManager,
	llamaCppMgr *service.LlamaCppManager,
	modelTesting *service.ModelTestingFramework,
	redis *repository.RedisRepo,
	configPath string,
) *ManageHandler {
	return &ManageHandler{
		scheduler:    scheduler,
		gpuMonitor:   gpuMonitor,
		sysCtl:       sysCtl,
		sysCollector: sysCollector,
		metrics:      metrics,
		cache:        cache,
		cacheUpdater: cacheUpdater,
		wsManager:    wsManager,
		vllmManager:  vllmManager,
		llamaCppMgr:  llamaCppMgr,
		modelTesting: modelTesting,
		redis:        redis,
		configPath:   configPath,
	}
}

func (h *ManageHandler) waitForModelReady(ctx context.Context, modelName string) error {
	port := h.scheduler.GetModelPort(modelName)
	if err := h.vllmManager.WaitUntilReady(ctx, port, 90*time.Second, time.Second); err != nil {
		return fmt.Errorf("model %s readiness probe failed: %w", modelName, err)
	}
	return nil
}

func (h *ManageHandler) proxyPythonManage(c *gin.Context, method string, path string, body interface{}) {
	baseURL := "http://localhost:35000"
	var reqBody *bytes.Reader
	if body != nil {
		payload, err := json.Marshal(body)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}
		reqBody = bytes.NewReader(payload)
	} else {
		reqBody = bytes.NewReader(nil)
	}

	req, err := http.NewRequestWithContext(c.Request.Context(), method, baseURL+path, reqBody)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"error": err.Error()})
		return
	}
	defer resp.Body.Close()

	var data interface{}
	if err := json.NewDecoder(resp.Body).Decode(&data); err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"error": err.Error()})
		return
	}
	c.JSON(resp.StatusCode, data)
}

func (h *ManageHandler) RegisterRoutes(rg *gin.RouterGroup) {
	m := rg.Group("/manage")
	{
		m.GET("/gpu", h.GetGPUStatus)
		m.GET("/gpu/summary", h.GetGPUSummary)
		m.GET("/gpu/history", h.GetGPUHistory)
		m.POST("/gpu/history/config", h.ConfigureGPUHistory)
		m.GET("/models", h.GetModelStatus)
		m.GET("/models/summary", h.ModelsSummary)
		m.GET("/models/aggregated", h.GetAggregatedModels)
		m.POST("/models/:model_name/start", h.StartModel)
		m.POST("/models/:model_name/stop", h.StopModel)
		m.POST("/models/:model_name/switch", h.SwitchModel)
		m.POST("/switch/atomic", h.AtomicSwitchModel)
		m.GET("/switch/status", h.GetAtomicSwitchStatus)
		m.DELETE("/switch/cancel", h.CancelAtomicSwitch)
		m.GET("/default-model", h.GetDefaultModel)
		m.POST("/default-model/:model_name", h.SetDefaultModel)
		m.DELETE("/default-model", h.ClearDefaultModel)
		m.GET("/queue", h.GetQueueStatus)
		m.GET("/preload", h.GetPreload)
		m.POST("/preload/:model_name", h.PreloadModel)
		m.GET("/preload/status", h.GetPreloadStatus)
		m.POST("/preload/:model_name/enable", h.EnablePreload)
		m.POST("/preload/:model_name/disable", h.DisablePreload)
		m.GET("/preload/all", h.EnableAllPreload)
		m.GET("/token/stats", h.GetTokenStats)
		m.GET("/token-stats", h.GetTokenStats)
		m.GET("/metrics", h.GetMetrics)
		m.POST("/metrics/reset", h.ResetMetrics)
		m.GET("/health/alert", h.CheckAlertStatus)
		m.GET("/cache/status", h.GetCacheStatus)
		m.POST("/cache/refresh", h.RefreshCache)
		m.GET("/cache/stats", h.GetCacheStats)
		m.GET("/config", h.GetConfig)
		m.PUT("/config", h.UpdateConfig)
		m.POST("/config/reload", h.ReloadConfig)
		m.GET("/service/status", h.GetServiceStatus)
		m.POST("/service/start", h.StartService)
		m.POST("/service/stop", h.StopService)
		m.POST("/service/restart", h.RestartService)
		m.GET("/system/status", h.SystemStatus)
		m.GET("/system/history", h.GetSystemHistory)
		m.GET("/token/history", h.GetTokenHistory)
		m.GET("/websocket/connections", h.GetWebSocketConnections)
		m.GET("/redis/health", h.RedisHealth)
		m.GET("/redis/keys", h.RedisKeys)
		m.DELETE("/redis/flush", h.RedisFlush)
		m.GET("/monitor/all", h.MonitorAll)
		m.GET("/gpu/enhanced", h.GetGPUEnhancedInfo)
		m.GET("/gpu/processes", h.GetGPUProcesses)
		m.GET("/vllm/metrics", h.GetVLLMMetrics)
		m.GET("/llama_cpp/models", h.GetLlamaCppModels)
		m.GET("/llama_cpp/status", h.GetLlamaCppStatus)
		m.POST("/llama_cpp/:model_name/start", h.StartLlamaCppModel)
		m.POST("/llama_cpp/:model_name/stop", h.StopLlamaCppModel)
		m.GET("/llama_cpp/:model_name/status", h.GetLlamaCppModelStatus)
		m.GET("/vllm/models", h.GetVLLMModels)
		m.GET("/metrics/health-detail", h.GetHealthDetail)
		m.GET("/gpu/memory-optimization", h.GetMemoryOptimization)
	}

	v1 := rg.Group("/v1")
	{
		v1.POST("/test/model/:model_name", h.RunModelTest)
		v1.GET("/test/reports", h.GetTestHistory)
		v1.GET("/test/results/:model_name", h.GetTestResults)
		v1.GET("/test/report/:model_name", h.GetTestResults)
		v1.POST("/test/comparative", h.RunComparativeAnalysis)
		v1.GET("/test/status", h.GetTestStatus)
		v1.DELETE("/test/reports", h.ClearTestReports)
		v1.POST("/test/model/:model_name/switch-and-test", h.SwitchAndTestModel)
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
	cacheKey := "api:manage:gpu:summary"
	if cached := h.cache.Get(cacheKey); cached != nil {
		c.JSON(http.StatusOK, cached)
		return
	}

	status := h.gpuMonitor.GetStatus()
	history := h.metrics.GetGPUHistory(20)

	if status == nil {
		result := gin.H{"status": "unavailable", "current": nil, "history": history}
		h.cache.Set(cacheKey, result, 30)
		c.JSON(http.StatusOK, result)
		return
	}

	current := gin.H{
		"name":               status.Name,
		"gpu_count":          status.GPUCount,
		"utilization":        status.Utilization,
		"temperature":        status.Temperature,
		"power_draw":         status.PowerDraw,
		"power_limit":        status.PowerLimit,
		"power_percent":      status.PowerPercent,
		"memory_utilization": status.MemoryUtilization,
		"used_memory":        status.UsedMemory,
		"available_memory":   status.AvailableMemory,
		"total_memory":       status.TotalMemory,
	}

	result := gin.H{
		"status":       "available",
		"current":      current,
		"history":      history,
		"health_score": h.gpuMonitor.GetHealthScore(),
	}
	h.cache.Set(cacheKey, result, 30)
	c.JSON(http.StatusOK, result)
}

func (h *ManageHandler) GetGPUHistory(c *gin.Context) {
	limit := 100
	if v := c.Query("limit"); v != "" {
		if n, err := fmt.Sscanf(v, "%d", &limit); err == nil && n > 0 {
			_ = n
		}
	}
	count := c.Query("count")
	if count != "" {
		if n, err := fmt.Sscanf(count, "%d", &limit); err == nil && n > 0 {
			_ = n
		}
	}
	history := h.metrics.GetGPUHistory(limit)
	c.JSON(http.StatusOK, gin.H{
		"history":   history,
		"count":     len(history),
		"enabled":   true,
		"max_days":  30,
		"timestamp": time.Now().Format(time.RFC3339),
	})
}

func (h *ManageHandler) ConfigureGPUHistory(c *gin.Context) {
	var req struct {
		Enabled bool `json:"enabled"`
		MaxDays int  `json:"max_days"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"status": "configured", "enabled": req.Enabled, "max_days": req.MaxDays})
}

func (h *ManageHandler) GetModelStatus(c *gin.Context) {
	models := h.scheduler.GetAvailableModels()
	status := make(map[string]interface{})
	for _, m := range models {
		mc := h.scheduler.GetModelConfig(m)
		status[m] = gin.H{
			"running":                   h.scheduler.IsModelRunning(m),
			"port":                      h.scheduler.GetModelPort(m),
			"service":                   h.scheduler.GetModelService(m),
			"active_requests":           h.scheduler.GetActiveRequests(m),
			"preloaded":                 h.scheduler.IsModelPreloaded(m),
			"supports_images":           h.scheduler.GetModelSupportsImages(m),
			"supports_tool_calling":     h.scheduler.GetModelSupportsToolCalling(m),
			"supports_image_generation": h.scheduler.GetModelSupportsImageGeneration(m),
			"last_used":                 nil,
			"description": func() string {
				if mc != nil {
					return mc.Description
				}
				return ""
			}(),
			"required_memory": func() string {
				if mc != nil {
					return mc.RequiredMemory
				}
				return ""
			}(),
			"backend_type": func() string {
				if mc != nil {
					return mc.Service
				}
				return ""
			}(),
		}
	}
	c.JSON(http.StatusOK, status)
}

func (h *ManageHandler) ModelsSummary(c *gin.Context) {
	cacheKey := "api:manage:models:summary"
	if cached := h.cache.Get(cacheKey); cached != nil {
		c.JSON(http.StatusOK, cached)
		return
	}

	models := h.scheduler.GetAvailableModels()
	summary := make([]map[string]interface{}, 0)
	for _, m := range models {
		mc := h.scheduler.GetModelConfig(m)
		entry := gin.H{
			"name":                      m,
			"running":                   h.scheduler.IsModelRunning(m),
			"preloaded":                 h.scheduler.IsModelPreloaded(m),
			"port":                      h.scheduler.GetModelPort(m),
			"supports_images":           h.scheduler.GetModelSupportsImages(m),
			"supports_tool_calling":     h.scheduler.GetModelSupportsToolCalling(m),
			"supports_image_generation": h.scheduler.GetModelSupportsImageGeneration(m),
		}
		if mc != nil {
			entry["description"] = mc.Description
			entry["required_memory"] = mc.RequiredMemory
			entry["backend_type"] = mc.Service
		}
		summary = append(summary, entry)
	}

	result := gin.H{
		"models":        summary,
		"total":         len(summary),
		"running_model": h.scheduler.GetCurrentModelName(),
	}
	h.cache.Set(cacheKey, result, 3)
	c.JSON(http.StatusOK, result)
}

func (h *ManageHandler) GetAggregatedModels(c *gin.Context) {
	h.proxyPythonManage(c, http.MethodGet, "/manage/models/aggregated", nil)
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
	body := gin.H{
		"model_name":     modelName,
		"set_as_default": true,
	}
	h.proxyPythonManage(c, http.MethodPost, "/manage/switch/atomic", body)
}

func (h *ManageHandler) AtomicSwitchModel(c *gin.Context) {
	var body map[string]interface{}
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	h.proxyPythonManage(c, http.MethodPost, "/manage/switch/atomic", body)
}

func (h *ManageHandler) GetAtomicSwitchStatus(c *gin.Context) {
	h.proxyPythonManage(c, http.MethodGet, "/manage/switch/status", nil)
}

func (h *ManageHandler) CancelAtomicSwitch(c *gin.Context) {
	h.proxyPythonManage(c, http.MethodDelete, "/manage/switch/cancel", nil)
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
	cacheKey := "api:manage:queue:status"
	if cached := h.cache.Get(cacheKey); cached != nil {
		c.JSON(http.StatusOK, cached)
		return
	}

	models := h.scheduler.GetAvailableModels()
	info := make(map[string]interface{})
	for _, m := range models {
		info[m] = gin.H{
			"active_requests":   h.scheduler.GetActiveRequests(m),
			"concurrency_limit": h.scheduler.GetConcurrencyLimit(),
			"can_accept":        h.scheduler.CanAcceptRequest(m),
		}
	}
	h.cache.Set(cacheKey, info, 3)
	c.JSON(http.StatusOK, info)
}

func (h *ManageHandler) GetPreload(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"preloaded_models": h.scheduler.GetPreloadedModels(),
		"all_models":       h.scheduler.GetAvailableModels(),
	})
}

func (h *ManageHandler) GetPreloadStatus(c *gin.Context) {
	models := h.scheduler.GetAvailableModels()
	details := make([]map[string]interface{}, 0)
	for _, m := range models {
		mc := h.scheduler.GetModelConfig(m)
		details = append(details, gin.H{
			"name":      m,
			"preloaded": h.scheduler.IsModelPreloaded(m),
			"running":   h.scheduler.IsModelRunning(m),
			"keep_alive": func() bool {
				if mc != nil {
					return mc.KeepAlive
				}
				return false
			}(),
		})
	}
	c.JSON(http.StatusOK, gin.H{
		"models":    details,
		"timestamp": time.Now().Format(time.RFC3339),
	})
}

func (h *ManageHandler) PreloadModel(c *gin.Context) {
	modelName := c.Param("model_name")
	if !h.scheduler.IsModelAvailable(modelName) {
		c.JSON(http.StatusNotFound, gin.H{"error": fmt.Sprintf("Model not found: %s", modelName)})
		return
	}
	h.scheduler.SchedulePreload(modelName)
	ok, _ := h.scheduler.StartModel(c.Request.Context(), modelName)
	if ok {
		c.JSON(http.StatusOK, gin.H{"status": "preloaded", "model": modelName})
	} else {
		c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("Failed to preload model %s", modelName)})
	}
}

func (h *ManageHandler) EnablePreload(c *gin.Context) {
	modelName := c.Param("model_name")
	if !h.scheduler.IsModelAvailable(modelName) {
		c.JSON(http.StatusNotFound, gin.H{"error": fmt.Sprintf("Model not found: %s", modelName)})
		return
	}
	h.scheduler.SchedulePreload(modelName)
	c.JSON(http.StatusOK, gin.H{"status": "enabled", "model": modelName})
}

func (h *ManageHandler) DisablePreload(c *gin.Context) {
	modelName := c.Param("model_name")
	if !h.scheduler.IsModelAvailable(modelName) {
		c.JSON(http.StatusNotFound, gin.H{"error": fmt.Sprintf("Model not found: %s", modelName)})
		return
	}
	h.scheduler.CancelPreload(modelName)
	c.JSON(http.StatusOK, gin.H{"status": "disabled", "model": modelName})
}

func (h *ManageHandler) EnableAllPreload(c *gin.Context) {
	models := h.scheduler.GetAvailableModels()
	for _, m := range models {
		h.scheduler.SchedulePreload(m)
	}
	c.JSON(http.StatusOK, gin.H{"status": "all_enabled", "count": len(models)})
}

func (h *ManageHandler) GetTokenStats(c *gin.Context) {
	cacheKey := "api:manage:token:stats"
	if cached := h.cache.Get(cacheKey); cached != nil {
		c.JSON(http.StatusOK, cached)
		return
	}
	stats := h.metrics.GetTokenStats()
	models := make(map[string]interface{})
	for _, m := range h.scheduler.GetAvailableModels() {
		// TODO: Add per-model token tracking in MetricsCollector
		models[m] = map[string]interface{}{
			"prompt_tokens":     0,
			"completion_tokens": 0,
			"total_tokens":      0,
		}
	}
	result := gin.H{
		"total_prompt_tokens":     stats.PromptTokens,
		"total_completion_tokens": stats.CompletionTokens,
		"total_tokens":            stats.TotalTokens,
		"prompt_tokens":           stats.PromptTokens,
		"completion_tokens":       stats.CompletionTokens,
		"models":                  models,
		"history":                 stats.History,
		"timestamp":               stats.Timestamp,
	}
	h.cache.Set(cacheKey, result, 10)
	c.JSON(http.StatusOK, result)
}

func (h *ManageHandler) GetMetrics(c *gin.Context) {
	cacheKey := "api:manage:metrics"
	if cached := h.cache.Get(cacheKey); cached != nil {
		c.JSON(http.StatusOK, cached)
		return
	}
	result := h.metrics.GetMetrics()
	h.cache.Set(cacheKey, result, 10)
	c.JSON(http.StatusOK, result)
}

func (h *ManageHandler) ResetMetrics(c *gin.Context) {
	h.metrics.Reset()
	h.cache.Delete("api:manage:metrics")
	c.JSON(http.StatusOK, gin.H{"status": "reset"})
}

func (h *ManageHandler) CheckAlertStatus(c *gin.Context) {
	cacheKey := "api:manage:health:alert"
	if cached := h.cache.Get(cacheKey); cached != nil {
		c.JSON(http.StatusOK, cached)
		return
	}

	gpuStatus := h.gpuMonitor.GetStatus()
	vllmMetrics := h.gpuMonitor.GetVLLMMetrics()
	healthInfo := h.metrics.GetComprehensiveHealthScore(gpuStatus, vllmMetrics)
	alertStatus := h.metrics.GetOverallAlertStatus(gpuStatus)
	overallScore := 0.0
	if v, ok := healthInfo["overall"].(float64); ok {
		overallScore = v
	}

	alertReasons := make([]string, 0)
	gpuAlerts := h.metrics.GetGPUAlerts(h.gpuMonitor.GetStatus())
	for _, a := range gpuAlerts {
		alertReasons = append(alertReasons, a.Message)
	}
	result := gin.H{
		"should_alert":  overallScore < 70,
		"health_score":  overallScore,
		"status":        healthInfo["status"],
		"alert_status":  alertStatus,
		"alert_reasons": alertReasons,
		"timestamp":     time.Now().Format(time.RFC3339),
	}
	h.cache.Set(cacheKey, result, 10)
	c.JSON(http.StatusOK, result)
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
	h.cache.Delete("api:" + endpoint)
	c.JSON(http.StatusOK, gin.H{"status": "refreshed", "endpoint": endpoint})
}

func (h *ManageHandler) GetCacheStats(c *gin.Context) {
	c.JSON(http.StatusOK, h.cache.GetStats())
}

func (h *ManageHandler) GetConfig(c *gin.Context) {
	cfg := config.Get()
	if cfg == nil {
		c.JSON(http.StatusOK, gin.H{
			"models":  h.scheduler.GetAvailableModels(),
			"message": "Config not loaded",
		})
		return
	}
	modelDetails := make(map[string]interface{})
	for name, mc := range cfg.Models {
		modelDetails[name] = gin.H{
			"service":                   mc.Service,
			"port":                      mc.Port,
			"required_memory":           mc.RequiredMemory,
			"preload":                   mc.Preload,
			"keep_alive":                mc.KeepAlive,
			"model_path":                mc.ModelPath,
			"supports_images":           mc.SupportsImages,
			"supports_tool_calling":     mc.SupportsToolCalling,
			"supports_image_generation": mc.SupportsImageGeneration,
			"description":               mc.Description,
			"concurrency_limit":         mc.ConcurrencyLimit,
		}
	}
	c.JSON(http.StatusOK, gin.H{
		"models":    modelDetails,
		"settings":  cfg.Settings,
		"vllm":      cfg.VLLM,
		"llama_cpp": cfg.LlamaCpp,
	})
}

func (h *ManageHandler) UpdateConfig(c *gin.Context) {
	var updates map[string]interface{}
	if err := c.ShouldBindJSON(&updates); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	cfg, err := config.Load(h.configPath)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("Failed to load config: %v", err)})
		return
	}

	if models, ok := updates["models"].(map[string]interface{}); ok {
		for name, v := range models {
			if mData, ok := v.(map[string]interface{}); ok {
				mc := config.ModelConfig{}
				if s, ok := mData["service"].(string); ok {
					mc.Service = s
				}
				if p, ok := mData["port"].(float64); ok {
					mc.Port = int(p)
				}
				if rm, ok := mData["required_memory"].(string); ok {
					mc.RequiredMemory = rm
				}
				if pre, ok := mData["preload"].(bool); ok {
					mc.Preload = pre
				}
				if ka, ok := mData["keep_alive"].(bool); ok {
					mc.KeepAlive = ka
				}
				if mp, ok := mData["model_path"].(string); ok {
					mc.ModelPath = mp
				}
				if desc, ok := mData["description"].(string); ok {
					mc.Description = desc
				}
				if si, ok := mData["supports_images"].(bool); ok {
					mc.SupportsImages = si
				}
				cfg.Models[name] = mc
			}
		}
	}

	if err := config.Save(h.configPath, cfg); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("Failed to save config: %v", err)})
		return
	}

	h.scheduler.SetConfig(cfg)
	c.JSON(http.StatusOK, gin.H{"status": "updated", "message": "Config saved and applied"})
}

func (h *ManageHandler) ReloadConfig(c *gin.Context) {
	cfg, err := config.Load(h.configPath)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("Failed to reload config: %v", err)})
		return
	}
	h.scheduler.SetConfig(cfg)
	c.JSON(http.StatusOK, gin.H{"status": "reloaded", "models_count": len(cfg.Models)})
}

func (h *ManageHandler) GetServiceStatus(c *gin.Context) {
	serviceName := c.Query("service")
	if serviceName == "" {
		serviceName = "vllm"
	}
	status := h.sysCtl.GetServiceStatus(serviceName)
	info := h.sysCtl.GetServiceInfo(serviceName)
	c.JSON(http.StatusOK, gin.H{
		"service": serviceName,
		"status":  status,
		"info":    info,
	})
}

func (h *ManageHandler) StartService(c *gin.Context) {
	var req struct {
		Service string `json:"service" binding:"required"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	ok := h.sysCtl.StartService(req.Service)
	if ok {
		c.JSON(http.StatusOK, gin.H{"status": "started", "service": req.Service})
	} else {
		c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("Failed to start service %s", req.Service)})
	}
}

func (h *ManageHandler) StopService(c *gin.Context) {
	var req struct {
		Service string `json:"service" binding:"required"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	ok := h.sysCtl.StopService(req.Service)
	if ok {
		c.JSON(http.StatusOK, gin.H{"status": "stopped", "service": req.Service})
	} else {
		c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("Failed to stop service %s", req.Service)})
	}
}

func (h *ManageHandler) RestartService(c *gin.Context) {
	var req struct {
		Service string `json:"service" binding:"required"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	ok := h.sysCtl.RestartService(req.Service)
	if ok {
		c.JSON(http.StatusOK, gin.H{"status": "restarted", "service": req.Service})
	} else {
		c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("Failed to restart service %s", req.Service)})
	}
}

func (h *ManageHandler) SystemStatus(c *gin.Context) {
	cacheKey := "api:manage:system:status"
	if cached := h.cache.Get(cacheKey); cached != nil {
		c.JSON(http.StatusOK, cached)
		return
	}
	result := h.sysCollector.GetSystemStatus()
	h.cache.Set(cacheKey, result, 10)
	c.JSON(http.StatusOK, result)
}

func (h *ManageHandler) GetSystemHistory(c *gin.Context) {
	limit := 60
	if v := c.Query("count"); v != "" {
		if n, err := fmt.Sscanf(v, "%d", &limit); err == nil && n > 0 {
			_ = n
		}
	}
	if v := c.Query("limit"); v != "" {
		if n, err := fmt.Sscanf(v, "%d", &limit); err == nil && n > 0 {
			_ = n
		}
	}
	history := h.sysCollector.GetSystemHistory(limit)
	c.JSON(http.StatusOK, gin.H{
		"history":   history,
		"count":     len(history),
		"timestamp": time.Now().Format(time.RFC3339),
	})
}

func (h *ManageHandler) GetTokenHistory(c *gin.Context) {
	limit := 60
	if v := c.Query("count"); v != "" {
		if n, err := fmt.Sscanf(v, "%d", &limit); err == nil && n > 0 {
			_ = n
		}
	}
	if v := c.Query("limit"); v != "" {
		if n, err := fmt.Sscanf(v, "%d", &limit); err == nil && n > 0 {
			_ = n
		}
	}
	stats := h.metrics.GetTokenStats()
	history := stats.History
	if limit > 0 && len(history) > limit {
		history = history[:limit]
	}

	frontendHistory := make([]gin.H, len(history))
	for i, entry := range history {
		frontendHistory[i] = gin.H{
			"timestamp":         entry.Timestamp,
			"total_tokens":      entry.Total,
			"prompt_tokens":     entry.Prompt,
			"completion_tokens": entry.Completion,
			"model_name":        entry.ModelName,
		}
	}

	c.JSON(http.StatusOK, gin.H{
		"history":   frontendHistory,
		"count":     len(frontendHistory),
		"timestamp": time.Now().Format(time.RFC3339),
	})
}

func (h *ManageHandler) GetWebSocketConnections(c *gin.Context) {
	c.JSON(http.StatusOK, h.wsManager.GetConnectionStats())
}

func (h *ManageHandler) RedisHealth(c *gin.Context) {
	if h.redis == nil || !h.redis.IsConnected() {
		c.JSON(http.StatusOK, gin.H{"status": "disconnected"})
		return
	}
	ctx := context.Background()
	info, err := h.redis.Info(ctx)
	if err != nil {
		c.JSON(http.StatusOK, gin.H{"status": "error", "error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"status": "connected", "info": info})
}

func (h *ManageHandler) RedisKeys(c *gin.Context) {
	if h.redis == nil || !h.redis.IsConnected() {
		c.JSON(http.StatusOK, gin.H{"keys": []string{}, "count": 0})
		return
	}
	pattern := c.Query("pattern")
	if pattern == "" {
		pattern = "ai_controller:*"
	}
	ctx := context.Background()
	keys, err := h.redis.Keys(ctx, pattern)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if len(keys) > 1000 {
		keys = keys[:1000]
	}
	c.JSON(http.StatusOK, gin.H{"keys": keys, "count": len(keys), "pattern": pattern})
}

func (h *ManageHandler) RedisFlush(c *gin.Context) {
	if h.redis == nil || !h.redis.IsConnected() {
		c.JSON(http.StatusOK, gin.H{"status": "no_redis"})
		return
	}
	ctx := context.Background()
	err := h.redis.FlushDB(ctx)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"status": "flushed"})
}

func (h *ManageHandler) MonitorAll(c *gin.Context) {
	gpuStatus := h.gpuMonitor.GetStatus()
	models := h.scheduler.GetAvailableModels()
	modelStatus := make(map[string]interface{})
	for _, m := range models {
		mc := h.scheduler.GetModelConfig(m)
		modelStatus[m] = gin.H{
			"running":         h.scheduler.IsModelRunning(m),
			"port":            h.scheduler.GetModelPort(m),
			"service":         h.scheduler.GetModelService(m),
			"active_requests": h.scheduler.GetActiveRequests(m),
			"preloaded":       h.scheduler.IsModelPreloaded(m),
			"backend_type": func() string {
				if mc != nil {
					return mc.Service
				}
				return ""
			}(),
		}
	}

	queueStatus := make(map[string]interface{})
	for _, m := range models {
		queueStatus[m] = gin.H{
			"active_requests": h.scheduler.GetActiveRequests(m),
			"can_accept":      h.scheduler.CanAcceptRequest(m),
		}
	}

	healthInfo := h.metrics.GetComprehensiveHealthScore(gpuStatus, h.gpuMonitor.GetVLLMMetrics())
	serviceStatus := gin.H{
		"vllm": h.sysCtl.GetServiceStatus("vllm"),
	}

	c.JSON(http.StatusOK, gin.H{
		"gpu":       gpuStatus,
		"models":    modelStatus,
		"queue":     queueStatus,
		"health":    healthInfo,
		"service":   serviceStatus,
		"system":    h.sysCollector.GetSystemStatus(),
		"timestamp": time.Now().Format(time.RFC3339),
	})
}

func (h *ManageHandler) GetLlamaCppModels(c *gin.Context) {
	ggufModels := h.llamaCppMgr.ScanGGUFModels()
	serverStatus := h.llamaCppMgr.GetServerStatus()
	c.JSON(http.StatusOK, gin.H{
		"gguf_models":     ggufModels,
		"running_servers": serverStatus,
		"timestamp":       time.Now().Format(time.RFC3339),
	})
}

func (h *ManageHandler) GetLlamaCppStatus(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"servers":   h.llamaCppMgr.GetServerStatus(),
		"timestamp": time.Now().Format(time.RFC3339),
	})
}

func (h *ManageHandler) GetVLLMModels(c *gin.Context) {
	models := h.vllmManager.ScanModels()
	serviceStatus := h.vllmManager.GetVLLMServiceStatus()
	c.JSON(http.StatusOK, gin.H{
		"available_models": models,
		"service_status":   serviceStatus,
		"timestamp":        time.Now().Format(time.RFC3339),
	})
}

func (h *ManageHandler) NodeIntegrationStatus(c *gin.Context) {
	gpuStatus := h.gpuMonitor.GetStatus()
	models := h.scheduler.GetAvailableModels()
	modelStatuses := make(map[string]interface{})
	for _, m := range models {
		modelStatuses[m] = gin.H{
			"available":                 h.scheduler.IsModelAvailable(m),
			"running":                   h.scheduler.IsModelRunning(m),
			"preloaded":                 h.scheduler.IsModelPreloaded(m),
			"port":                      h.scheduler.GetModelPort(m),
			"supports_images":           h.scheduler.GetModelSupportsImages(m),
			"supports_tool_calling":     h.scheduler.GetModelSupportsToolCalling(m),
			"supports_image_generation": h.scheduler.GetModelSupportsImageGeneration(m),
			"active_requests":           h.scheduler.GetActiveRequests(m),
			"can_accept":                h.scheduler.CanAcceptRequest(m),
		}
	}

	result := gin.H{
		"service": "ai-controller",
		"status": func() string {
			if gpuStatus != nil {
				return "healthy"
			}
			return "degraded"
		}(),
		"timestamp": time.Now().Format(time.RFC3339),
		"models":    modelStatuses,
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
		"name":                      modelName,
		"available":                 true,
		"running":                   h.scheduler.IsModelRunning(modelName),
		"preloaded":                 h.scheduler.IsModelPreloaded(modelName),
		"port":                      h.scheduler.GetModelPort(modelName),
		"model_path":                h.scheduler.GetModelPath(modelName),
		"service":                   h.scheduler.GetModelService(modelName),
		"supports_images":           h.scheduler.GetModelSupportsImages(modelName),
		"supports_tool_calling":     h.scheduler.GetModelSupportsToolCalling(modelName),
		"supports_image_generation": h.scheduler.GetModelSupportsImageGeneration(modelName),
		"active_requests":           h.scheduler.GetActiveRequests(modelName),
		"can_accept":                h.scheduler.CanAcceptRequest(modelName),
	}
	if mc != nil {
		info["description"] = mc.Description
		info["required_memory"] = mc.RequiredMemory
		info["backend_type"] = mc.Service
		info["keep_alive"] = mc.KeepAlive
	}
	c.JSON(http.StatusOK, info)
}

func (h *ManageHandler) RunModelTest(c *gin.Context) {
	modelName := c.Param("model_name")
	if !h.scheduler.IsModelAvailable(modelName) {
		c.JSON(http.StatusNotFound, gin.H{"error": fmt.Sprintf("Model not found: %s", modelName)})
		return
	}

	if !h.scheduler.IsModelRunning(modelName) {
		ok, err := h.scheduler.StartModel(c.Request.Context(), modelName)
		if !ok {
			c.JSON(http.StatusServiceUnavailable, gin.H{"error": fmt.Sprintf("Failed to start model: %v", err)})
			return
		}
		if err := h.waitForModelReady(c.Request.Context(), modelName); err != nil {
			c.JSON(http.StatusServiceUnavailable, gin.H{"error": err.Error()})
			return
		}
	}

	mc := h.scheduler.GetModelConfig(modelName)
	port := h.scheduler.GetModelPort(modelName)
	modelPath := h.scheduler.GetModelPath(modelName)

	report := h.modelTesting.RunAllTests(c.Request.Context(), modelName, modelPath, port, mc.SupportsImages)

	// Save to Redis
	if h.redis != nil && h.redis.IsConnected() {
		ctx := context.Background()
		historyKey := "model_test:history"
		reportKey := fmt.Sprintf("model_test:report:%s", modelName)

		// Save report
		h.redis.SetJSON(ctx, reportKey, report, 0)

		// Add to history
		historyEntry := gin.H{
			"model_name": modelName,
			"timestamp":  report.Timestamp,
			"status": func() string {
				if report.PassRate >= 1.0 {
					return "passed"
				}
				return "partial"
			}(),
			"pass_rate": report.PassRate,
		}
		data, _ := json.Marshal(historyEntry)
		h.redis.LPush(ctx, historyKey, string(data))
		h.redis.LTrim(ctx, historyKey, 0, 99)
	}

	c.JSON(http.StatusOK, gin.H{
		"status":  "completed",
		"message": fmt.Sprintf("Successfully tested %s", modelName),
		"report":  report,
	})
}

func (h *ManageHandler) GetTestHistory(c *gin.Context) {
	if h.redis == nil || !h.redis.IsConnected() {
		c.JSON(http.StatusOK, gin.H{
			"status":  "empty",
			"reports": gin.H{},
			"history": []interface{}{},
			"count":   0,
		})
		return
	}

	ctx := context.Background()
	items, err := h.redis.LRange(ctx, "model_test:history", 0, 99)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	result := make([]interface{}, 0)
	reports := make(map[string]interface{})
	for _, item := range items {
		var entry map[string]interface{}
		if err := json.Unmarshal([]byte(item), &entry); err == nil {
			result = append(result, entry)
			modelName, _ := entry["model_name"].(string)
			if modelName != "" {
				if _, exists := reports[modelName]; !exists {
					reports[modelName] = entry
				}
			}
		}
	}
	c.JSON(http.StatusOK, gin.H{
		"status":  "success",
		"reports": reports,
		"history": result,
		"count":   len(result),
	})
}

func (h *ManageHandler) GetTestResults(c *gin.Context) {
	modelName := c.Param("model_name")
	if h.redis == nil || !h.redis.IsConnected() {
		c.JSON(http.StatusNotFound, gin.H{"status": "not_found", "message": "Redis not connected"})
		return
	}

	ctx := context.Background()
	reportKey := fmt.Sprintf("model_test:report:%s", modelName)
	report, err := h.redis.Get(ctx, reportKey)
	if err != nil || report == "" {
		c.JSON(http.StatusNotFound, gin.H{"status": "not_found", "message": "Report not found"})
		return
	}

	var result interface{}
	json.Unmarshal([]byte(report), &result)
	c.JSON(http.StatusOK, gin.H{
		"status": "found",
		"report": result,
	})
}

func (h *ManageHandler) GetGPUEnhancedInfo(c *gin.Context) {
	enhanced := h.gpuMonitor.GetEnhancedInfo()
	if enhanced == nil {
		c.JSON(http.StatusOK, gin.H{"status": "unavailable", "message": "No GPU detected"})
		return
	}
	c.JSON(http.StatusOK, enhanced)
}

func (h *ManageHandler) GetGPUProcesses(c *gin.Context) {
	processes := h.gpuMonitor.GetGPUProcesses()
	if processes == nil {
		c.JSON(http.StatusOK, gin.H{"processes": []interface{}{}, "count": 0})
		return
	}
	c.JSON(http.StatusOK, gin.H{"processes": processes, "count": len(processes)})
}

func (h *ManageHandler) GetVLLMMetrics(c *gin.Context) {
	metrics := h.gpuMonitor.GetVLLMMetrics()
	c.JSON(http.StatusOK, metrics)
}

func (h *ManageHandler) GetHealthDetail(c *gin.Context) {
	gpuStatus := h.gpuMonitor.GetStatus()
	vllmMetrics := h.gpuMonitor.GetVLLMMetrics()
	healthScores := h.metrics.GetComprehensiveHealthScore(gpuStatus, vllmMetrics)
	gpuAlerts := h.metrics.GetGPUAlerts(gpuStatus)
	healthScore := h.gpuMonitor.GetHealthScore()
	c.JSON(http.StatusOK, gin.H{
		"health_scores":        healthScores,
		"gpu_alerts":           gpuAlerts,
		"health_score":         healthScore,
		"gpu_status_summary":   gpuStatus,
		"vllm_metrics_summary": vllmMetrics,
		"timestamp":            time.Now().Format(time.RFC3339),
	})
}
func (h *ManageHandler) StartLlamaCppModel(c *gin.Context) {
	modelName := c.Param("model_name")
	if !h.scheduler.IsModelAvailable(modelName) {
		c.JSON(http.StatusNotFound, gin.H{"error": fmt.Sprintf("Model not found: %s", modelName)})
		return
	}
	backendType := h.scheduler.GetModelBackendType(modelName)
	if backendType != "llama_cpp" {
		c.JSON(http.StatusBadRequest, gin.H{"error": fmt.Sprintf("Model %s is not a llama_cpp model (backend: %s)", modelName, backendType)})
		return
	}
	if h.llamaCppMgr.IsServerRunning(modelName) {
		c.JSON(http.StatusOK, gin.H{"status": "already_running", "model": modelName})
		return
	}
	err := h.llamaCppMgr.StartServerByName(c.Request.Context(), modelName)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("Failed to start llama_cpp model %s: %v", modelName, err)})
		return
	}
	h.scheduler.MarkModelSelected(modelName)
	c.JSON(http.StatusOK, gin.H{"status": "starting", "model": modelName, "backend_type": "llama_cpp"})
}

func (h *ManageHandler) StopLlamaCppModel(c *gin.Context) {
	modelName := c.Param("model_name")
	if !h.scheduler.IsModelAvailable(modelName) {
		c.JSON(http.StatusNotFound, gin.H{"error": fmt.Sprintf("Model not found: %s", modelName)})
		return
	}
	backendType := h.scheduler.GetModelBackendType(modelName)
	if backendType != "llama_cpp" {
		c.JSON(http.StatusBadRequest, gin.H{"error": fmt.Sprintf("Model %s is not a llama_cpp model (backend: %s)", modelName, backendType)})
		return
	}
	if !h.llamaCppMgr.IsServerRunning(modelName) {
		c.JSON(http.StatusOK, gin.H{"status": "already_stopped", "model": modelName})
		return
	}
	err := h.llamaCppMgr.StopServer(modelName)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("Failed to stop llama_cpp model %s: %v", modelName, err)})
		return
	}
	c.JSON(http.StatusOK, gin.H{"status": "stopped", "model": modelName, "backend_type": "llama_cpp"})
}

func (h *ManageHandler) GetLlamaCppModelStatus(c *gin.Context) {
	modelName := c.Param("model_name")
	status := h.llamaCppMgr.GetModelStatus(modelName)
	c.JSON(http.StatusOK, status)
}

func (h *ManageHandler) GetMemoryOptimization(c *gin.Context) {
	status := h.gpuMonitor.GetMemoryOptimizationStatus()
	c.JSON(http.StatusOK, status)
}

func (h *ManageHandler) RunComparativeAnalysis(c *gin.Context) {
	var req struct {
		ModelNames []string `json:"model_names"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if len(req.ModelNames) == 0 {
		c.JSON(http.StatusBadRequest, gin.H{"error": "model_names is required"})
		return
	}

	getModelInfo := func(modelName string) (string, int, bool) {
		mc := h.scheduler.GetModelConfig(modelName)
		if mc == nil {
			return "", 0, false
		}
		return mc.ModelPath, mc.Port, mc.SupportsImages
	}

	analysis := h.modelTesting.RunComparativeAnalysis(c.Request.Context(), req.ModelNames, getModelInfo)

	c.JSON(http.StatusOK, gin.H{
		"status":  "completed",
		"message": "Comparative analysis completed",
		"analysis": analysis,
	})
}

func (h *ManageHandler) GetTestStatus(c *gin.Context) {
	if h.redis == nil || !h.redis.IsConnected() {
		c.JSON(http.StatusOK, gin.H{
			"status":            "ready",
			"models_tested_count": 0,
			"models_tested":     []string{},
			"timestamp":         time.Now().Format(time.RFC3339),
		})
		return
	}

	ctx := context.Background()
	items, err := h.redis.LRange(ctx, "model_test:history", 0, -1)
	if err != nil {
		c.JSON(http.StatusOK, gin.H{
			"status":            "ready",
			"models_tested_count": 0,
			"models_tested":     []string{},
			"timestamp":         time.Now().Format(time.RFC3339),
		})
		return
	}

	modelsTested := make(map[string]bool)
	for _, item := range items {
		var entry map[string]any
		if err := json.Unmarshal([]byte(item), &entry); err == nil {
			if modelName, ok := entry["model_name"].(string); ok {
				modelsTested[modelName] = true
			}
		}
	}

	modelList := make([]string, 0, len(modelsTested))
	for m := range modelsTested {
		modelList = append(modelList, m)
	}

	c.JSON(http.StatusOK, gin.H{
		"status":            "ready",
		"models_tested_count": len(modelList),
		"models_tested":     modelList,
		"timestamp":         time.Now().Format(time.RFC3339),
	})
}

func (h *ManageHandler) ClearTestReports(c *gin.Context) {
	if h.redis == nil || !h.redis.IsConnected() {
		c.JSON(http.StatusOK, gin.H{"status": "success", "message": "No reports to clear"})
		return
	}

	ctx := context.Background()
	h.redis.Delete(ctx, "model_test:history")
	h.redis.Delete(ctx, "model_test:report:*")

	c.JSON(http.StatusOK, gin.H{"status": "success", "message": "All test reports cleared"})
}

func (h *ManageHandler) SwitchAndTestModel(c *gin.Context) {
	modelName := c.Param("model_name")
	if !h.scheduler.IsModelAvailable(modelName) {
		c.JSON(http.StatusNotFound, gin.H{"error": fmt.Sprintf("Model not found: %s", modelName)})
		return
	}

	h.scheduler.SetSwitchingInProgress(true)
	defer h.scheduler.SetSwitchingInProgress(false)

	ok, err := h.scheduler.StartModel(c.Request.Context(), modelName)
	if !ok {
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"status":  "failed",
			"message": fmt.Sprintf("Failed to switch to model %s", modelName),
			"report":  nil,
		})
		return
	}
	_ = err

	h.scheduler.MarkModelSelected(modelName)

	if err := h.waitForModelReady(c.Request.Context(), modelName); err != nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"status":  "failed",
			"message": fmt.Sprintf("Model switch successful but readiness check failed: %v", err),
			"report":  nil,
		})
		return
	}

	mc := h.scheduler.GetModelConfig(modelName)
	port := h.scheduler.GetModelPort(modelName)
	modelPath := h.scheduler.GetModelPath(modelName)

	report := h.modelTesting.RunAllTests(c.Request.Context(), modelName, modelPath, port, mc.SupportsImages)

	if h.redis != nil && h.redis.IsConnected() {
		ctx := context.Background()
		reportKey := fmt.Sprintf("model_test:report:%s", modelName)
		h.redis.SetJSON(ctx, reportKey, report, 0)

		historyKey := "model_test:history"
		historyEntry := gin.H{
			"model_name": modelName,
			"timestamp":  report.Timestamp,
			"status": func() string {
				if report.PassRate >= 1.0 {
					return "passed"
				}
				return "partial"
			}(),
			"pass_rate": report.PassRate,
		}
		data, _ := json.Marshal(historyEntry)
		h.redis.LPush(ctx, historyKey, string(data))
		h.redis.LTrim(ctx, historyKey, 0, 99)
	}

	c.JSON(http.StatusOK, gin.H{
		"status":  "completed",
		"message": fmt.Sprintf("Successfully switched to %s and completed tests", modelName),
		"report":  report,
	})
}
