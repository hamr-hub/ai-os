package middleware

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
	"go-vllm-api/internal/service"
)

type stubGPUMonitor struct {
	status *service.GPUStatus
}

func (m *stubGPUMonitor) GetStatus() *service.GPUStatus {
	return m.status
}

func TestEffectiveLimit_Normal(t *testing.T) {
	mw := NewRateLimitMiddleware(100, 60)
	got := mw.effectiveLimit()
	if got != 100 {
		t.Errorf("effectiveLimit without GPU monitor: got %d, want 100", got)
	}
}

func TestEffectiveLimit_GPUHealthy(t *testing.T) {
	mw := NewRateLimitMiddlewareWithGPU(100, 60, nil, &stubGPUMonitor{
		status: &service.GPUStatus{Utilization: 50, MemoryUtilization: 60},
	})
	got := mw.effectiveLimit()
	if got != 100 {
		t.Errorf("effectiveLimit with healthy GPU: got %d, want 100", got)
	}
}

func TestEffectiveLimit_GPUPressure(t *testing.T) {
	mw := NewRateLimitMiddlewareWithGPU(100, 60, nil, &stubGPUMonitor{
		status: &service.GPUStatus{Utilization: 90, MemoryUtilization: 60},
	})
	got := mw.effectiveLimit()
	if got != 50 {
		t.Errorf("effectiveLimit with GPU pressure: got %d, want 50 (degradeRatio=0.5)", got)
	}
}

func TestEffectiveLimit_MemoryPressure(t *testing.T) {
	mw := NewRateLimitMiddlewareWithGPU(100, 60, nil, &stubGPUMonitor{
		status: &service.GPUStatus{Utilization: 50, MemoryUtilization: 92},
	})
	got := mw.effectiveLimit()
	if got != 50 {
		t.Errorf("effectiveLimit with memory pressure: got %d, want 50", got)
	}
}

func TestEffectiveTokenLimit_Normal(t *testing.T) {
	mw := NewRateLimitMiddlewareWithGPU(100, 60, nil, &stubGPUMonitor{
		status: &service.GPUStatus{Utilization: 50, MemoryUtilization: 60},
	}).WithMaxTokens(100000)
	got := mw.effectiveTokenLimit()
	if got != 100000 {
		t.Errorf("effectiveTokenLimit with healthy GPU: got %d, want 100000", got)
	}
}

func TestEffectiveTokenLimit_GPUPressure(t *testing.T) {
	mw := NewRateLimitMiddlewareWithGPU(100, 60, nil, &stubGPUMonitor{
		status: &service.GPUStatus{Utilization: 90, MemoryUtilization: 90},
	}).WithMaxTokens(100000)
	got := mw.effectiveTokenLimit()
	if got != 50000 {
		t.Errorf("effectiveTokenLimit with GPU pressure: got %d, want 50000", got)
	}
}

func TestRateLimitMiddleware_ExemptIP(t *testing.T) {
	gin.SetMode(gin.TestMode)
	r := gin.New()
	mw := NewRateLimitMiddleware(10, 60)
	r.Use(mw.Handler())
	r.POST("/v1/chat/completions", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "ok"})
	})

	req := httptest.NewRequest("POST", "/v1/chat/completions", nil)
	req.RemoteAddr = "127.0.0.1:12345"
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("exempt IP should pass: got %d, want 200", w.Code)
	}
}

func TestRateLimitMiddleware_NonLimitedPath(t *testing.T) {
	gin.SetMode(gin.TestMode)
	r := gin.New()
	mw := NewRateLimitMiddleware(10, 60)
	r.Use(mw.Handler())
	r.GET("/v1/status", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "ok"})
	})

	req := httptest.NewRequest("GET", "/v1/status", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("non-limited path should pass: got %d, want 200", w.Code)
	}
}
