package service

import (
	"context"
	"time"

	"go.uber.org/zap"
)

type CacheUpdater struct {
	logger      *zap.Logger
	gpuMonitor  *GPUMonitor
	scheduler   *Scheduler
	cache       *CacheService
	cancel      context.CancelFunc
}

func NewCacheUpdater(gpuMonitor *GPUMonitor, scheduler *Scheduler, cache *CacheService, logger *zap.Logger) *CacheUpdater {
	return &CacheUpdater{
		logger:     logger,
		gpuMonitor: gpuMonitor,
		scheduler:  scheduler,
		cache:      cache,
	}
}

type updateTask struct {
	name     string
	interval time.Duration
	fn       func()
}

func (cu *CacheUpdater) Start(ctx context.Context, metrics *MetricsCollector) {
	ctx, cu.cancel = context.WithCancel(ctx)

	tasks := []updateTask{
		{"gpu_status", 3 * time.Second, cu.updateGPUStatus},
		{"gpu_summary", 10 * time.Second, cu.updateGPUSummary},
		{"model_status", 5 * time.Second, cu.updateModelStatus},
		{"queue_status", 3 * time.Second, cu.updateQueueStatus},
		{"system_status", 10 * time.Second, cu.updateSystemStatus},
		{"health", 5 * time.Second, cu.updateHealth},
		{"metrics", 10 * time.Second, func() { cu.updateMetrics(metrics) }},
		{"preload_status", 30 * time.Second, cu.updatePreloadStatus},
		{"models_list", 300 * time.Second, cu.updateModelsList},
		{"models_summary", 3 * time.Second, cu.updateModelsSummary},
	}

	cu.warmup(tasks)

	for _, task := range tasks {
		go cu.runTask(ctx, task)
	}
	cu.logger.Info("cache updater started")
}

func (cu *CacheUpdater) warmup(tasks []updateTask) {
	for _, task := range tasks {
		task.fn()
	}
}

func (cu *CacheUpdater) runTask(ctx context.Context, task updateTask) {
	ticker := time.NewTicker(task.interval)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			task.fn()
		}
	}
}

func (cu *CacheUpdater) Stop() {
	if cu.cancel != nil {
		cu.cancel()
	}
	cu.logger.Info("cache updater stopped")
}

func (cu *CacheUpdater) GetStatus() map[string]interface{} {
	return map[string]interface{}{
		"running": cu.cancel != nil,
	}
}

func (cu *CacheUpdater) updateGPUStatus() {
	status := cu.gpuMonitor.GetStatus()
	if status != nil {
		cu.cache.Set("api:manage:gpu:status", status, 10)
	}
}

func (cu *CacheUpdater) updateGPUSummary() {
	summary := cu.gpuMonitor.GetStatus()
	if summary != nil {
		cu.cache.Set("api:manage:gpu:summary", summary, 30)
	}
}

func (cu *CacheUpdater) updateModelStatus() {
	models := cu.scheduler.GetAvailableModels()
	status := make(map[string]interface{})
	for _, m := range models {
		status[m] = map[string]interface{}{
			"running":         cu.scheduler.IsModelRunning(m),
			"port":            cu.scheduler.GetModelPort(m),
			"service":         cu.scheduler.GetModelService(m),
			"active_requests": cu.scheduler.GetActiveRequests(m),
			"preloaded":       cu.scheduler.IsModelPreloaded(m),
		}
	}
	cu.cache.Set("api:manage:models:status", status, 5)
}

func (cu *CacheUpdater) updateQueueStatus() {
	models := cu.scheduler.GetAvailableModels()
	info := make(map[string]interface{})
	for _, m := range models {
		info[m] = map[string]interface{}{
			"active_requests":    cu.scheduler.GetActiveRequests(m),
			"concurrency_limit": cu.scheduler.GetConcurrencyLimit(),
			"can_accept":         cu.scheduler.CanAcceptRequest(m),
		}
	}
	cu.cache.Set("api:manage:queue:status", info, 3)
}

func (cu *CacheUpdater) updateSystemStatus() {
	cu.cache.Set("api:manage:system:status", map[string]interface{}{
		"timestamp": time.Now().Format(time.RFC3339),
	}, 10)
}

func (cu *CacheUpdater) updateHealth() {
	_ = cu.gpuMonitor.GetStatus()
	_ = cu.scheduler.rateLimiter
	cu.cache.Set("api:health", map[string]interface{}{
		"status":    "healthy",
		"timestamp": time.Now().Format(time.RFC3339),
	}, 5)
}

func (cu *CacheUpdater) updateMetrics(metrics *MetricsCollector) {
	cu.cache.Set("api:manage:metrics", metrics.GetMetrics(), 10)
}

func (cu *CacheUpdater) updatePreloadStatus() {
	preloaded := cu.scheduler.GetPreloadedModels()
	all := cu.scheduler.GetAvailableModels()
	status := make(map[string]interface{})
	for _, m := range all {
		status[m] = map[string]interface{}{
			"preloaded": contains(preloaded, m),
			"running":   cu.scheduler.IsModelRunning(m),
		}
	}
	cu.cache.Set("api:manage:preload:detailed", map[string]interface{}{
		"preloaded_models": preloaded,
		"all_models":       all,
		"status":           status,
	}, 30)
}

func (cu *CacheUpdater) updateModelsList() {
	models := cu.scheduler.GetAvailableModels()
	list := make([]map[string]interface{}, 0)
	for _, m := range models {
		mc := cu.scheduler.GetModelConfig(m)
		if mc != nil {
			list = append(list, map[string]interface{}{
				"id":               m,
				"object":           "model",
				"running":          cu.scheduler.IsModelRunning(m),
				"supports_images":  mc.SupportsImages,
				"description":      mc.Description,
				"port":             mc.Port,
			})
		}
	}
	cu.cache.Set("api:v1:models", map[string]interface{}{
		"object": "list",
		"data":   list,
	}, 300)
}

func (cu *CacheUpdater) updateModelsSummary() {
	models := cu.scheduler.GetAvailableModels()
	summary := make([]map[string]interface{}, 0)
	for _, m := range models {
		mc := cu.scheduler.GetModelConfig(m)
		if mc != nil {
			summary = append(summary, map[string]interface{}{
				"name":              m,
				"running":           cu.scheduler.IsModelRunning(m),
				"supports_images":   mc.SupportsImages,
				"description":       mc.Description,
				"required_memory":   mc.RequiredMemory,
				"port":              mc.Port,
			})
		}
	}
	cu.cache.Set("api:manage:models:summary", map[string]interface{}{
		"models":        summary,
		"total":         len(summary),
		"running_model": cu.scheduler.GetCurrentModelName(),
	}, 5)
}

func contains(slice []string, item string) bool {
	for _, s := range slice {
		if s == item {
			return true
		}
	}
	return false
}
