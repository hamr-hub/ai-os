package middleware

import (
	"fmt"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"go-vllm-api/internal/service"
)

type RateLimiterMiddleware struct {
	maxRequests int
	window      time.Duration
	limiter     *service.RateLimiter
	exemptIPs   map[string]bool
}

func NewRateLimitMiddleware(maxRequests int, windowSeconds int) *RateLimiterMiddleware {
	return &RateLimiterMiddleware{
		maxRequests: maxRequests,
		window:      time.Duration(windowSeconds) * time.Second,
		exemptIPs: map[string]bool{
			"127.0.0.1": true,
			"localhost": true,
			"::1":       true,
		},
	}
}

func NewRateLimitMiddlewareWithLimiter(maxRequests int, windowSeconds int, limiter *service.RateLimiter) *RateLimiterMiddleware {
	return &RateLimiterMiddleware{
		maxRequests: maxRequests,
		window:      time.Duration(windowSeconds) * time.Second,
		limiter:     limiter,
		exemptIPs: map[string]bool{
			"127.0.0.1": true,
			"localhost": true,
			"::1":       true,
		},
	}
}

func (rl *RateLimiterMiddleware) Handler() gin.HandlerFunc {
	return func(c *gin.Context) {
		ip := c.ClientIP()
		if rl.exemptIPs[ip] {
			c.Next()
			return
		}

		if rl.limiter != nil {
			if !rl.limiter.CanAcceptClientRequest(ip, rl.maxRequests) {
				c.AbortWithStatusJSON(http.StatusTooManyRequests, gin.H{
					"error": "rate limit exceeded",
				})
				return
			}
		}

		c.Header("X-RateLimit-Limit", fmt.Sprintf("%d", rl.maxRequests))
		c.Header("X-RateLimit-Remaining", fmt.Sprintf("%d", 0))
		c.Next()
	}
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
