package service

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"go-vllm-api/internal/repository"

	"go.uber.org/zap"
)

type MetricsCollector struct {
	logger       *zap.Logger
	redis        *repository.RedisRepo
	requestCount atomic.Int64
	errorCount   atomic.Int64
	totalLatency atomic.Int64

	promptTokens     atomic.Int64
	completionTokens atomic.Int64
	totalTokens      atomic.Int64

	mu           sync.RWMutex
	tokenHistory []TokenHistoryEntry
	metrics      map[string]interface{}
}

type TokenStats struct {
	PromptTokens     int64               `json:"total_prompt_tokens"`
	CompletionTokens int64               `json:"total_completion_tokens"`
	TotalTokens      int64               `json:"total_tokens"`
	History          []TokenHistoryEntry `json:"history"`
	Timestamp        string              `json:"timestamp"`
}

type TokenHistoryEntry struct {
	Timestamp  string `json:"timestamp"`
	Total      int64  `json:"total"`
	Prompt     int64  `json:"prompt"`
	Completion int64  `json:"completion"`
	ModelName  string `json:"model_name"`
}

type GPUHistoryEntry struct {
	Timestamp            string  `json:"timestamp"`
	Temperature          int     `json:"temperature"`
	Utilization          int     `json:"utilization"`
	UsedMemory           int64   `json:"used_memory"`
	AvailableMemory      int64   `json:"available_memory"`
	TotalMemory          int64   `json:"total_memory"`
	PowerDraw            int     `json:"power_draw"`
	PowerPercent         int     `json:"power_percent"`
	MemoryUtilization    int     `json:"memory_utilization"`
	EccErrors            int     `json:"ecc_errors"`
	VLLMRunningRequests  int     `json:"vllm_running_requests,omitempty"`
	VLLMWaitingRequests  int     `json:"vllm_waiting_requests,omitempty"`
	VLLMGPUCacheUsage    float64 `json:"vllm_gpu_cache_usage,omitempty"`
}

type AlertInfo struct {
	Type      string  `json:"type"`
	Severity  string  `json:"severity"`
	Value     float64 `json:"value"`
	Threshold float64 `json:"threshold"`
	Message   string  `json:"message"`
}

func NewMetricsCollector(redis *repository.RedisRepo, logger *zap.Logger) *MetricsCollector {
	m := &MetricsCollector{
		logger:       logger,
		redis:        redis,
		metrics:      make(map[string]interface{}),
		tokenHistory: make([]TokenHistoryEntry, 0),
	}
	m.loadFromRedis()
	return m
}

func (m *MetricsCollector) loadFromRedis() {
	if m.redis == nil || !m.redis.IsConnected() {
		return
	}

	ctx := context.Background()
	// Load token usage
	val, err := m.redis.Get(ctx, "ai_controller:metrics:token_usage")
	if err == nil && val != "" {
		var usage map[string]int64
		if err := json.Unmarshal([]byte(val), &usage); err == nil {
			m.promptTokens.Store(usage["total_prompt_tokens"])
			m.completionTokens.Store(usage["total_completion_tokens"])
			m.totalTokens.Store(usage["total_tokens"])
		}
	}

	// Load token history
	val, err = m.redis.Get(ctx, "ai_controller:metrics:token_history")
	if err == nil && val != "" {
		m.mu.Lock()
		json.Unmarshal([]byte(val), &m.tokenHistory)
		m.mu.Unlock()
	}
}

func (m *MetricsCollector) saveToRedis() {
	if m.redis == nil || !m.redis.IsConnected() {
		return
	}

	ctx := context.Background()
	// Save token usage
	usage := map[string]int64{
		"total_prompt_tokens":     m.promptTokens.Load(),
		"total_completion_tokens": m.completionTokens.Load(),
		"total_tokens":            m.totalTokens.Load(),
	}
	m.redis.SetJSON(ctx, "ai_controller:metrics:token_usage", usage, 0)

	// Save token history
	m.mu.RLock()
	m.redis.SetJSON(ctx, "ai_controller:metrics:token_history", m.tokenHistory, 0)
	m.mu.RUnlock()
}

func (m *MetricsCollector) RecordRequest(endpoint string, statusCode int, responseTime float64, opts ...RecordOption) {
	m.requestCount.Add(1)
	if statusCode >= 400 {
		m.errorCount.Add(1)
	}
	m.totalLatency.Add(int64(responseTime * 1000))

	var opt RecordOptions
	for _, o := range opts {
		o(&opt)
	}

	if opt.PromptTokens > 0 || opt.CompletionTokens > 0 {
		m.promptTokens.Add(opt.PromptTokens)
		m.completionTokens.Add(opt.CompletionTokens)
		m.totalTokens.Add(opt.PromptTokens + opt.CompletionTokens)

		// Record history entry
		m.mu.Lock()
		m.tokenHistory = append(m.tokenHistory, TokenHistoryEntry{
			Timestamp:  time.Now().Format(time.RFC3339),
			Total:      m.totalTokens.Load(),
			Prompt:     m.promptTokens.Load(),
			Completion: m.completionTokens.Load(),
			ModelName:  opt.Model,
		})
		if len(m.tokenHistory) > 500 {
			m.tokenHistory = m.tokenHistory[len(m.tokenHistory)-500:]
		}
		m.mu.Unlock()
		m.saveToRedis()
	}

	if m.redis != nil && m.redis.IsConnected() {
		ctx := context.Background()
		key := "ai_controller:metrics:requests"
		entry := map[string]interface{}{
			"endpoint":          endpoint,
			"status_code":       statusCode,
			"response_time":     responseTime,
			"timestamp":         time.Now().Format(time.RFC3339),
			"model":             opt.Model,
			"is_image":          opt.IsImage,
			"image_size":        opt.ImageSize,
			"prompt_tokens":     opt.PromptTokens,
			"completion_tokens": opt.CompletionTokens,
			"total_tokens":      opt.PromptTokens + opt.CompletionTokens,
		}
		data, _ := json.Marshal(entry)
		m.redis.LPush(ctx, key, string(data))
		m.redis.LTrim(ctx, key, 0, 999)
	}
}

type RecordOptions struct {
	Model            string
	IsImage          bool
	ImageSize        int64
	PromptTokens     int64
	CompletionTokens int64
	TotalTokens      int64
}

type RecordOption func(*RecordOptions)

func WithModel(model string) RecordOption {
	return func(o *RecordOptions) { o.Model = model }
}

func WithImage(isImage bool, size int64) RecordOption {
	return func(o *RecordOptions) { o.IsImage = isImage; o.ImageSize = size }
}

func WithTokens(prompt, completion, total int64) RecordOption {
	return func(o *RecordOptions) {
		o.PromptTokens = prompt
		o.CompletionTokens = completion
		o.TotalTokens = total
	}
}

func (m *MetricsCollector) GetMetrics() map[string]interface{} {
	req := m.requestCount.Load()
	return map[string]interface{}{
		"total_requests": req,
		"total_errors":   m.errorCount.Load(),
		"avg_latency_ms": func() float64 {
			if req == 0 {
				return 0
			}
			return float64(m.totalLatency.Load()) / float64(req)
		}(),
		"token_stats": m.GetTokenStats(),
	}
}

func (m *MetricsCollector) GetTokenStats() TokenStats {
	m.mu.RLock()
	defer m.mu.RUnlock()

	history := make([]TokenHistoryEntry, len(m.tokenHistory))
	copy(history, m.tokenHistory)

	return TokenStats{
		PromptTokens:     m.promptTokens.Load(),
		CompletionTokens: m.completionTokens.Load(),
		TotalTokens:      m.totalTokens.Load(),
		History:          history,
		Timestamp:        time.Now().Format(time.RFC3339),
	}
}

func (m *MetricsCollector) Reset() {
	m.requestCount.Store(0)
	m.errorCount.Store(0)
	m.totalLatency.Store(0)
	m.promptTokens.Store(0)
	m.completionTokens.Store(0)
	m.totalTokens.Store(0)
	m.mu.Lock()
	m.tokenHistory = make([]TokenHistoryEntry, 0)
	m.mu.Unlock()

	if m.redis != nil && m.redis.IsConnected() {
		ctx := context.Background()
		m.redis.Delete(ctx, "ai_controller:metrics:token_usage")
		m.redis.Delete(ctx, "ai_controller:metrics:token_history")
	}
}

func (m *MetricsCollector) GetComprehensiveHealthScore(gpuStatus *GPUStatus) map[string]interface{} {
	serviceScore := m.calculateServiceScore()
	gpuScore := m.calculateGPUScore(gpuStatus)
	responseScore := m.calculateResponseScore()

	overall := serviceScore*0.4 + gpuScore*0.3 + responseScore*0.3
	status := "healthy"
	if overall < 50 {
		status = "critical"
	} else if overall < 70 {
		status = "warning"
	} else if overall < 85 {
		status = "degraded"
	}

	return map[string]interface{}{
		"overall":        overall,
		"status":         status,
		"service_score":  serviceScore,
		"gpu_score":      gpuScore,
		"response_score": responseScore,
		"alerts":         m.GetGPUAlerts(gpuStatus),
	}
}

func (m *MetricsCollector) calculateServiceScore() float64 {
	req := m.requestCount.Load()
	if req == 0 {
		return 100.0
	}
	errRate := float64(m.errorCount.Load()) / float64(req)
	return 100.0 - errRate*100
}

func (m *MetricsCollector) calculateGPUScore(gpuStatus *GPUStatus) float64 {
	if gpuStatus == nil {
		return 50.0
	}
	tempScore := 100.0
	if gpuStatus.Temperature > 85 {
		tempScore = 100.0 - float64(gpuStatus.Temperature-85)*2
		if gpuStatus.Temperature > 95 {
			tempScore = 0
		}
	}
	memScore := 100.0
	memUtil := float64(gpuStatus.MemoryUtilization)
	if memUtil > 0.9 {
		memScore = 100.0 - (memUtil-0.9)*1000
		if memUtil > 0.95 {
			memScore = 0
		}
	}
	return (tempScore + memScore) / 2
}

func (m *MetricsCollector) calculateResponseScore() float64 {
	req := m.requestCount.Load()
	if req == 0 {
		return 100.0
	}
	avgLatency := float64(m.totalLatency.Load()) / float64(req) / 1000.0
	score := 100.0 - avgLatency*10
	if score < 0 {
		score = 0
	}
	return score
}

func (m *MetricsCollector) GetGPUAlerts(gpuStatus *GPUStatus) []AlertInfo {
	if gpuStatus == nil {
		return nil
	}
	var alerts []AlertInfo

	if gpuStatus.Temperature > 85 {
		severity := "warning"
		if gpuStatus.Temperature > 95 {
			severity = "critical"
		}
		alerts = append(alerts, AlertInfo{
			Type:      "temperature",
			Severity:  severity,
			Value:     float64(gpuStatus.Temperature),
			Threshold: 85,
			Message:   fmt.Sprintf("GPU temperature %dC exceeds threshold", gpuStatus.Temperature),
		})
	}

	memUtil := float64(gpuStatus.MemoryUtilization)
	if memUtil > 90 {
		severity := "warning"
		if memUtil > 95 {
			severity = "critical"
		}
		alerts = append(alerts, AlertInfo{
			Type:      "memory",
			Severity:  severity,
			Value:     memUtil,
			Threshold: 90,
			Message:   fmt.Sprintf("GPU memory utilization %d%% exceeds threshold", gpuStatus.MemoryUtilization),
		})
	}

	if gpuStatus.PowerLimit > 0 && gpuStatus.PowerPercent > 85 {
		severity := "warning"
		if gpuStatus.PowerPercent > 95 {
			severity = "critical"
		}
		alerts = append(alerts, AlertInfo{
			Type:      "power",
			Severity:  severity,
			Value:     float64(gpuStatus.PowerPercent),
			Threshold: 85,
			Message:   fmt.Sprintf("GPU power %d%% exceeds threshold", gpuStatus.PowerPercent),
		})
	}

	if gpuStatus.Primary != nil && gpuStatus.Primary.EccErrors > 0 {
		alerts = append(alerts, AlertInfo{
			Type:      "ecc_errors",
			Severity:  "warning",
			Value:     float64(gpuStatus.Primary.EccErrors),
			Threshold: 0,
			Message:   fmt.Sprintf("GPU ECC errors detected: %d", gpuStatus.Primary.EccErrors),
		})
	}

	if gpuStatus.Primary != nil && len(gpuStatus.Primary.ThrottleReasons) > 0 {
		alerts = append(alerts, AlertInfo{
			Type:      "throttle",
			Severity:  "warning",
			Value:     float64(len(gpuStatus.Primary.ThrottleReasons)),
			Threshold: 0,
			Message:   fmt.Sprintf("GPU throttling: %s", strings.Join(gpuStatus.Primary.ThrottleReasons, ", ")),
		})
	}

	if gpuStatus.VLLMMetrics != nil {
		if gpuStatus.VLLMMetrics.WaitingRequests > 10 {
			severity := "warning"
			if gpuStatus.VLLMMetrics.WaitingRequests > 50 {
				severity = "critical"
			}
			alerts = append(alerts, AlertInfo{
				Type:      "vllm_queue",
				Severity:  severity,
				Value:     float64(gpuStatus.VLLMMetrics.WaitingRequests),
				Threshold: 10,
				Message:   fmt.Sprintf("vLLM queue overflow: %d waiting requests", gpuStatus.VLLMMetrics.WaitingRequests),
			})
		}
		if gpuStatus.VLLMMetrics.GPUCacheUsage > 90 {
			alerts = append(alerts, AlertInfo{
				Type:      "vllm_cache",
				Severity:  "warning",
				Value:     gpuStatus.VLLMMetrics.GPUCacheUsage,
				Threshold: 90,
				Message:   fmt.Sprintf("vLLM KV cache usage %.1f%% exceeds threshold", gpuStatus.VLLMMetrics.GPUCacheUsage),
			})
		}
	}

	return alerts
}

func (m *MetricsCollector) GetOverallAlertStatus(gpuStatus *GPUStatus) map[string]interface{} {
	alerts := m.GetGPUAlerts(gpuStatus)
	status := "ok"
	for _, a := range alerts {
		if a.Severity == "critical" {
			status = "critical"
			break
		}
		if a.Severity == "warning" && status != "critical" {
			status = "warning"
		}
	}
	return map[string]interface{}{
		"status":  status,
		"alerts":  alerts,
		"count":   len(alerts),
	}
}

func (m *MetricsCollector) SaveGPUHistory(gpuStatus *GPUStatus) {
	if m.redis == nil || !m.redis.IsConnected() || gpuStatus == nil {
		return
	}
	ctx := context.Background()
	key := "gpu:history"
	entry := GPUHistoryEntry{
		Timestamp:         time.Now().Format(time.RFC3339),
		Temperature:       gpuStatus.Temperature,
		Utilization:       gpuStatus.Utilization,
		UsedMemory:        gpuStatus.UsedMemory,
		AvailableMemory:   gpuStatus.AvailableMemory,
		TotalMemory:       gpuStatus.TotalMemory,
		PowerDraw:         gpuStatus.PowerDraw,
		PowerPercent:      gpuStatus.PowerPercent,
		MemoryUtilization: gpuStatus.MemoryUtilization,
	}
	if gpuStatus.Primary != nil {
		entry.EccErrors = gpuStatus.Primary.EccErrors
	}
	if gpuStatus.VLLMMetrics != nil {
		entry.VLLMRunningRequests = gpuStatus.VLLMMetrics.RunningRequests
		entry.VLLMWaitingRequests = gpuStatus.VLLMMetrics.WaitingRequests
		entry.VLLMGPUCacheUsage = gpuStatus.VLLMMetrics.GPUCacheUsage
	}
	data, _ := json.Marshal(entry)
	m.redis.LPush(ctx, key, string(data))
	m.redis.LTrim(ctx, key, 0, 129599)
	m.redis.Expire(ctx, key, 30*24*time.Hour)
}

func (m *MetricsCollector) GetGPUHistory(limit int) []GPUHistoryEntry {
	if m.redis == nil || !m.redis.IsConnected() {
		return nil
	}
	ctx := context.Background()
	key := "gpu:history"
	items, err := m.redis.LRange(ctx, key, 0, int64(limit-1))
	if err != nil {
		return nil
	}
	var entries []GPUHistoryEntry
	for _, item := range items {
		var entry GPUHistoryEntry
		if err := json.Unmarshal([]byte(item), &entry); err == nil {
			entries = append(entries, entry)
		}
	}
	return entries
}

func (m *MetricsCollector) GetDetailedMetrics() map[string]interface{} {
	base := m.GetMetrics()
	base["health"] = m.GetComprehensiveHealthScore(nil)
	return base
}

func (m *MetricsCollector) GetAlertReasons() []string {
	var reasons []string
	return reasons
}
