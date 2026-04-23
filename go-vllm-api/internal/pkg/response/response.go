package response

import (
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
)

type APIResponse struct {
	Success   bool        `json:"success"`
	Data      interface{} `json:"data,omitempty"`
	Error     string      `json:"error,omitempty"`
	Code      int         `json:"code"`
	Timestamp string      `json:"timestamp"`
}

func OK(c *gin.Context, data interface{}) {
	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      data,
		Code:      0,
		Timestamp: time.Now().Format(time.RFC3339),
	})
}

func Error(c *gin.Context, status int, msg string) {
	c.JSON(status, APIResponse{
		Success:   false,
		Error:     msg,
		Code:      status,
		Timestamp: time.Now().Format(time.RFC3339),
	})
}

func RawJSON(c *gin.Context, data interface{}) {
	c.JSON(http.StatusOK, data)
}
