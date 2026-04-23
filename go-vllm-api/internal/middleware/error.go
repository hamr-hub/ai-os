package middleware

import (
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
)

func ErrorHandler() gin.HandlerFunc {
	return func(c *gin.Context) {
		c.Next()
		if len(c.Errors) > 0 {
			err := c.Errors.Last()
			status := http.StatusInternalServerError
			if err.Type == gin.ErrorTypePublic {
				status = http.StatusBadRequest
			}
			c.AbortWithStatusJSON(status, gin.H{
				"error":     err.Error(),
				"code":      status,
				"timestamp": time.Now().Format(time.RFC3339),
				"path":      c.Request.URL.Path,
			})
		}
	}
}
