package middleware

import (
	"strings"

	"github.com/gin-gonic/gin"
)

func CORS(allowedOrigins []string) gin.HandlerFunc {
	originSet := map[string]bool{}
	for _, origin := range allowedOrigins {
		if trimmed := strings.TrimSpace(origin); trimmed != "" {
			originSet[trimmed] = true
		}
	}
	if len(originSet) == 0 {
		originSet["http://localhost:30001"] = true
		originSet["http://localhost:30000"] = true
	}

	return func(c *gin.Context) {
		origin := c.GetHeader("Origin")
		if originSet["*"] {
			c.Header("Access-Control-Allow-Origin", "*")
		} else if originSet[origin] {
			c.Header("Access-Control-Allow-Origin", origin)
			c.Header("Vary", "Origin")
		}
		c.Header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS,PATCH")
		c.Header("Access-Control-Allow-Headers", "*")
		c.Header("Access-Control-Allow-Credentials", "false")
		c.Header("Access-Control-Max-Age", "86400")
		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(204)
			return
		}
		c.Next()
	}
}
