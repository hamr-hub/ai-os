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
		id := uuid.New().String()
		c.Set("request_id", id)
		c.Header("X-Request-ID", id)
		c.Next()
	}
}

func RequestTracking(logger *zap.Logger) gin.HandlerFunc {
	return func(c *gin.Context) {
		start := time.Now()
		c.Next()
		duration := time.Since(start).Seconds()
		requestID, _ := c.Get("request_id")
		clientIP := c.ClientIP()
		modelName, _ := c.Get("model")
		reqSize := c.Request.ContentLength
		respSize := c.Writer.Size()

		fields := []zap.Field{
			zap.String("request_id", fmt.Sprintf("%v", requestID)),
			zap.String("method", c.Request.Method),
			zap.String("path", c.Request.URL.Path),
			zap.String("query", c.Request.URL.RawQuery),
			zap.Int("status", c.Writer.Status()),
			zap.Float64("duration_s", duration),
			zap.String("client_ip", clientIP),
			zap.Int64("request_size", reqSize),
			zap.Int("response_size", respSize),
		}

		if modelName != nil {
			fields = append(fields, zap.String("model", fmt.Sprintf("%v", modelName)))
		}

		if c.Writer.Status() >= 400 {
			logger.Warn("request", fields...)
		} else {
			logger.Info("request", fields...)
		}
	}
}
