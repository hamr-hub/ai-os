package middleware

import (
	"fmt"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
)

const (
	ErrCodeBadRequest       = 40000
	ErrCodeUnauthorized     = 40100
	ErrCodeForbidden        = 40300
	ErrCodeNotFound         = 40400
	ErrCodeRateLimited      = 42900
	ErrCodeInternal         = 50000
	ErrCodeServiceUnavailable = 50300
	ErrCodeBadGateway       = 50200
	ErrCodeCircuitOpen      = 50301
	ErrCodeModelNotReady    = 50302
	ErrCodeModelNotFound    = 40401
	ErrCodeQueueFull        = 42901
)

type APIError struct {
	Code      int    `json:"code"`
	Message   string `json:"message"`
	HTTPStatus int   `json:"-"`
	Path      string `json:"path,omitempty"`
	RequestID string `json:"request_id,omitempty"`
	Timestamp string `json:"timestamp"`
}

func (e *APIError) Error() string {
	return fmt.Sprintf("[%d] %s", e.Code, e.Message)
}

func NewAPIError(code int, message string, httpStatus int) *APIError {
	return &APIError{
		Code:      code,
		Message:   message,
		HTTPStatus: httpStatus,
		Timestamp: time.Now().Format(time.RFC3339),
	}
}

func RespondWithError(c *gin.Context, apiErr *APIError) {
	if requestID, exists := c.Get("request_id"); exists {
		apiErr.RequestID = fmt.Sprintf("%v", requestID)
	}
	apiErr.Path = c.Request.URL.Path
	c.AbortWithStatusJSON(apiErr.HTTPStatus, apiErr)
}

func ErrorHandler() gin.HandlerFunc {
	return func(c *gin.Context) {
		c.Next()
		if len(c.Errors) > 0 {
			err := c.Errors.Last()
			status := http.StatusInternalServerError
			code := ErrCodeInternal
			if err.Type == gin.ErrorTypePublic {
				status = http.StatusBadRequest
				code = ErrCodeBadRequest
			}
			c.AbortWithStatusJSON(status, &APIError{
				Code:      code,
				Message:   err.Error(),
				HTTPStatus: status,
				Path:      c.Request.URL.Path,
				Timestamp: time.Now().Format(time.RFC3339),
			})
		}
	}
}
