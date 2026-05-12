package middleware

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"go-vllm-api/internal/config"

	"github.com/gin-gonic/gin"
)

func TestAdminAuthRejectsMissingToken(t *testing.T) {
	gin.SetMode(gin.TestMode)
	r := gin.New()
	r.Use(NewAdminAuthMiddleware(config.AuthConfig{APIKeys: []string{"secret-token"}}).Handler())
	r.GET("/manage/protected", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"ok": true})
	})

	req := httptest.NewRequest("GET", "/manage/protected", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusUnauthorized {
		t.Fatalf("missing token status = %d, want %d", w.Code, http.StatusUnauthorized)
	}
}

func TestAdminAuthAcceptsBearerToken(t *testing.T) {
	gin.SetMode(gin.TestMode)
	r := gin.New()
	r.Use(NewAdminAuthMiddleware(config.AuthConfig{APIKeys: []string{"secret-token"}}).Handler())
	r.GET("/manage/protected", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"ok": true})
	})

	req := httptest.NewRequest("GET", "/manage/protected", nil)
	req.Header.Set("Authorization", "Bearer secret-token")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("valid token status = %d, want %d", w.Code, http.StatusOK)
	}
}

func TestCORSAllowsConfiguredOriginOnly(t *testing.T) {
	gin.SetMode(gin.TestMode)
	r := gin.New()
	r.Use(CORS([]string{"http://localhost:30000"}))
	r.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"ok": true})
	})

	allowedReq := httptest.NewRequest("GET", "/health", nil)
	allowedReq.Header.Set("Origin", "http://localhost:30000")
	allowed := httptest.NewRecorder()
	r.ServeHTTP(allowed, allowedReq)
	if got := allowed.Header().Get("Access-Control-Allow-Origin"); got != "http://localhost:30000" {
		t.Fatalf("allowed origin header = %q", got)
	}

	blockedReq := httptest.NewRequest("GET", "/health", nil)
	blockedReq.Header.Set("Origin", "https://example.com")
	blocked := httptest.NewRecorder()
	r.ServeHTTP(blocked, blockedReq)
	if got := blocked.Header().Get("Access-Control-Allow-Origin"); got != "" {
		t.Fatalf("blocked origin header = %q, want empty", got)
	}
}
