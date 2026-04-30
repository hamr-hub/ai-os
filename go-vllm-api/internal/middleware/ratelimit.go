package middleware

import (
	"fmt"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"go-vllm-api/internal/service"
)

type GPUMonitorAccessor interface {
	GetStatus() *service.GPUStatus
}

type RateLimiterMiddleware struct {
	maxRequests      int
	maxTokens        int
	window           time.Duration
	limiter          *service.RateLimiter
	gpuMonitor       GPUMonitorAccessor
	exemptIPs        map[string]bool
	rateLimitedPaths []string
	gpuThreshold     int
	degradeRatio     float64
}

func NewRateLimitMiddleware(maxRequests int, windowSeconds int) *RateLimiterMiddleware {
	return &RateLimiterMiddleware{
		maxRequests: maxRequests,
		maxTokens:   0,
		window:      time.Duration(windowSeconds) * time.Second,
		exemptIPs: map[string]bool{
			"127.0.0.1": true,
			"localhost": true,
			"::1":       true,
		},
		rateLimitedPaths: []string{
			"/v1/chat/completions",
			"/v1/completions",
			"/v1/embeddings",
			"/v1/images/generations",
		},
		gpuThreshold: 85,
		degradeRatio: 0.5,
	}
}

func NewRateLimitMiddlewareWithLimiter(maxRequests int, windowSeconds int, limiter *service.RateLimiter) *RateLimiterMiddleware {
	return &RateLimiterMiddleware{
		maxRequests: maxRequests,
		maxTokens:   0,
		window:      time.Duration(windowSeconds) * time.Second,
		limiter:     limiter,
		exemptIPs: map[string]bool{
			"127.0.0.1": true,
			"localhost": true,
			"::1":       true,
		},
		rateLimitedPaths: []string{
			"/v1/chat/completions",
			"/v1/completions",
			"/v1/embeddings",
			"/v1/images/generations",
		},
		gpuThreshold: 85,
		degradeRatio: 0.5,
	}
}

func NewRateLimitMiddlewareWithGPU(maxRequests int, windowSeconds int, limiter *service.RateLimiter, gpuMonitor GPUMonitorAccessor) *RateLimiterMiddleware {
	return &RateLimiterMiddleware{
		maxRequests: maxRequests,
		maxTokens:   0,
		window:      time.Duration(windowSeconds) * time.Second,
		limiter:     limiter,
		gpuMonitor:  gpuMonitor,
		exemptIPs: map[string]bool{
			"127.0.0.1": true,
			"localhost": true,
			"::1":       true,
		},
		rateLimitedPaths: []string{
			"/v1/chat/completions",
			"/v1/completions",
			"/v1/embeddings",
			"/v1/images/generations",
		},
		gpuThreshold: 85,
		degradeRatio: 0.5,
	}
}

func (rl *RateLimiterMiddleware) WithMaxTokens(maxTokens int) *RateLimiterMiddleware {
	rl.maxTokens = maxTokens
	return rl
}

func (rl *RateLimiterMiddleware) WithGPUThreshold(threshold int) *RateLimiterMiddleware {
	rl.gpuThreshold = threshold
	return rl
}

func (rl *RateLimiterMiddleware) isRateLimitedPath(path string) bool {
	for _, limitedPath := range rl.rateLimitedPaths {
		if path == limitedPath {
			return true
		}
	}
	return false
}

func (rl *RateLimiterMiddleware) effectiveLimit() int {
	if rl.gpuMonitor == nil {
		return rl.maxRequests
	}
	status := rl.gpuMonitor.GetStatus()
	if status == nil {
		return rl.maxRequests
	}
	if status.Utilization > rl.gpuThreshold || status.MemoryUtilization > rl.gpuThreshold {
		degraded := int(float64(rl.maxRequests) * rl.degradeRatio)
		if degraded < 1 {
			degraded = 1
		}
		return degraded
	}
	return rl.maxRequests
}

func (rl *RateLimiterMiddleware) Handler() gin.HandlerFunc {
	return func(c *gin.Context) {
		if !rl.isRateLimitedPath(c.Request.URL.Path) {
			c.Next()
			return
		}

		ip := GetRealClientIP(c)
		if rl.exemptIPs[ip] {
			c.Header("X-RateLimit-Limit", fmt.Sprintf("%d", rl.maxRequests))
			c.Header("X-RateLimit-Remaining", fmt.Sprintf("%d", rl.maxRequests))
			if rl.maxTokens > 0 {
				c.Header("X-RateLimit-Tokens-Limit", fmt.Sprintf("%d", rl.maxTokens))
			}
			c.Next()
			return
		}

		effectiveLimit := rl.effectiveLimit()
		isDegraded := effectiveLimit < rl.maxRequests

		if rl.limiter != nil {
			if !rl.limiter.CanAcceptClientRequest(ip, effectiveLimit) {
				c.Header("X-RateLimit-Limit", fmt.Sprintf("%d", effectiveLimit))
				c.Header("X-RateLimit-Remaining", "0")
				if isDegraded {
					c.Header("X-RateLimit-Degraded", "true")
					c.Header("Retry-After", "60")
					c.AbortWithStatusJSON(http.StatusTooManyRequests, gin.H{
						"error":   "rate limit exceeded (GPU under pressure, limits reduced)",
						"degraded": true,
					})
				} else {
					c.AbortWithStatusJSON(http.StatusTooManyRequests, gin.H{
						"error": "rate limit exceeded",
					})
				}
				return
			}

			if rl.maxTokens > 0 {
				tokenCountStr := c.GetHeader("X-Token-Count")
				if tokenCountStr != "" {
					var tokenCount int
					fmt.Sscanf(tokenCountStr, "%d", &tokenCount)
					if tokenCount > 0 && !rl.limiter.AddTokenCount(ip, tokenCount, rl.effectiveTokenLimit()) {
						c.Header("X-RateLimit-Limit", fmt.Sprintf("%d", effectiveLimit))
						c.Header("X-RateLimit-Remaining", "0")
						c.Header("X-RateLimit-Tokens-Limit", fmt.Sprintf("%d", rl.effectiveTokenLimit()))
						c.Header("X-RateLimit-Tokens-Remaining", "0")
						c.AbortWithStatusJSON(http.StatusTooManyRequests, gin.H{
							"error": "token rate limit exceeded",
						})
						return
					}
				}
			}

			used := rl.limiter.GetClientRequestCount(ip)
			remaining := effectiveLimit - used
			if remaining < 0 {
				remaining = 0
			}
			c.Header("X-RateLimit-Limit", fmt.Sprintf("%d", effectiveLimit))
			c.Header("X-RateLimit-Remaining", fmt.Sprintf("%d", remaining))
			if rl.maxTokens > 0 {
				tokenUsed := rl.limiter.GetTokenCount(ip)
				tokenRemaining := rl.effectiveTokenLimit() - tokenUsed
				if tokenRemaining < 0 {
					tokenRemaining = 0
				}
				c.Header("X-RateLimit-Tokens-Limit", fmt.Sprintf("%d", rl.effectiveTokenLimit()))
				c.Header("X-RateLimit-Tokens-Remaining", fmt.Sprintf("%d", tokenRemaining))
			}
			if isDegraded {
				c.Header("X-RateLimit-Degraded", "true")
			}
		}
		c.Next()
	}
}

func (rl *RateLimiterMiddleware) effectiveTokenLimit() int {
	if rl.gpuMonitor == nil || rl.maxTokens <= 0 {
		return rl.maxTokens
	}
	status := rl.gpuMonitor.GetStatus()
	if status == nil {
		return rl.maxTokens
	}
	if status.Utilization > rl.gpuThreshold || status.MemoryUtilization > rl.gpuThreshold {
		degraded := int(float64(rl.maxTokens) * rl.degradeRatio)
		if degraded < 1 {
			degraded = 1
		}
		return degraded
	}
	return rl.maxTokens
}

func Timeout(seconds int) gin.HandlerFunc {
	return func(c *gin.Context) {
		if seconds <= 0 {
			c.Next()
			return
		}
		done := make(chan struct{})
		go func() {
			c.Next()
			close(done)
		}()
		select {
		case <-done:
		case <-time.After(time.Duration(seconds) * time.Second):
			c.AbortWithStatusJSON(http.StatusGatewayTimeout, gin.H{
				"error":  "request timeout",
				"timeout": seconds,
			})
		}
	}
}
