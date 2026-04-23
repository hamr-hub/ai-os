package service

import (
	"context"
	"encoding/json"
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
	mu           sync.RWMutex
	metrics      map[string]interface{}
}

func NewMetricsCollector(redis *repository.RedisRepo, logger *zap.Logger) *MetricsCollector {
	return &MetricsCollector{
		logger:  logger,
		redis:   redis,
		metrics: make(map[string]interface{}),
	}
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

	if m.redis != nil && m.redis.IsConnected() {
		ctx := context.Background()
		key := "ai_controller:metrics:requests"
		entry := map[string]interface{}{
			"endpoint":        endpoint,
			"status_code":     statusCode,
			"response_time":   responseTime,
			"timestamp":       time.Now().Format(time.RFC3339),
			"model":           opt.Model,
			"is_image":        opt.IsImage,
			"image_size":      opt.ImageSize,
		}
		data, _ := json.Marshal(entry)
		m.redis.LPush(ctx, key, string(data))
		m.redis.LTrim(ctx, key, 0, 999)
	}
}

type RecordOptions struct {
	Model     string
	IsImage   bool
	ImageSize int64
}

type RecordOption func(*RecordOptions)

func WithModel(model string) RecordOption {
	return func(o *RecordOptions) { o.Model = model }
}

func WithImage(isImage bool, size int64) RecordOption {
	return func(o *RecordOptions) { o.IsImage = isImage; o.ImageSize = size }
}

func (m *MetricsCollector) GetMetrics() map[string]interface{} {
	return map[string]interface{}{
		"total_requests": m.requestCount.Load(),
		"total_errors":   m.errorCount.Load(),
		"avg_latency_ms": func() float64 {
			req := m.requestCount.Load()
			if req == 0 {
				return 0
			}
			return float64(m.totalLatency.Load()) / float64(req)
		}(),
	}
}

func (m *MetricsCollector) Reset() {
	m.requestCount.Store(0)
	m.errorCount.Store(0)
	m.totalLatency.Store(0)
}

func (m *MetricsCollector) GetComprehensiveHealthScore(gpuStatus *GPUStatus) map[string]interface{} {
	serviceScore := 80.0
	if gpuStatus != nil {
		serviceScore = 100.0
	}
	gpuScore := 70.0
	if gpuStatus != nil && gpuStatus.Temperature < 80 && gpuStatus.Utilization < 90 {
		gpuScore = 95.0
	}
	responseScore := 85.0

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
		"overall":       overall,
		"status":        status,
		"service_score": serviceScore,
		"gpu_score":     gpuScore,
		"response_score": responseScore,
	}
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
