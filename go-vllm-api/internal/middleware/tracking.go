package middleware

import (
	"fmt"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"go.uber.org/zap"
)

func RequestID() gin.HandlerFunc {
	return func(c *gin.Context) {
		id := c.GetHeader("X-Request-ID")
		if id == "" {
			id = uuid.New().String()
		}
		c.Set("request_id", id)
		c.Header("X-Request-ID", id)
		c.Next()
	}
}

func RecordTiming(c *gin.Context, stage string, duration time.Duration) {
	if timings, exists := c.Get("timings"); exists {
		t := timings.(map[string]float64)
		t[stage] = duration.Seconds()
	} else {
		t := map[string]float64{stage: duration.Seconds()}
		c.Set("timings", t)
	}
}

func RequestTracking(logger *zap.Logger) gin.HandlerFunc {
	return func(c *gin.Context) {
		start := time.Now()
		c.Set("timings", map[string]float64{})
		c.Next()
		duration := time.Since(start)
		requestID, _ := c.Get("request_id")
		clientIP := GetRealClientIP(c)
		modelName, _ := c.Get("model")
		reqSize := c.Request.ContentLength
		respSize := c.Writer.Size()
		rateLimited, _ := c.Get("rate_limited")
		upstream, _ := c.Get("upstream")

		timings, _ := c.Get("timings")
		timingMap := timings.(map[string]float64)
		timingMap["total"] = duration.Seconds()

		fields := []zap.Field{
			zap.String("request_id", fmt.Sprintf("%v", requestID)),
			zap.String("method", c.Request.Method),
			zap.String("path", c.Request.URL.Path),
			zap.String("query", c.Request.URL.RawQuery),
			zap.Int("status", c.Writer.Status()),
			zap.Float64("duration_s", duration.Seconds()),
			zap.String("client_ip", clientIP),
			zap.Int64("request_size", reqSize),
			zap.Int("response_size", respSize),
		}

		if modelName != nil {
			fields = append(fields, zap.String("model", fmt.Sprintf("%v", modelName)))
		}

		if rateLimited != nil {
			fields = append(fields, zap.Bool("rate_limited", true))
		}

		if upstream != nil {
			fields = append(fields, zap.String("upstream", fmt.Sprintf("%v", upstream)))
		}

		for stage, dur := range timingMap {
			if stage != "total" {
				fields = append(fields, zap.Float64(fmt.Sprintf("timing_%s_s", stage), dur))
			}
		}

		if c.Writer.Status() >= 400 {
			logger.Warn("request", fields...)
		} else {
			logger.Info("request", fields...)
		}
	}
}
