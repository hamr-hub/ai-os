package middleware

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
)

func newTestRequestWithRemote(remoteAddr string, forwardedFor string) *http.Request {
	req := httptest.NewRequest("GET", "/health", nil)
	req.RemoteAddr = remoteAddr
	if forwardedFor != "" {
		req.Header.Set("X-Forwarded-For", forwardedFor)
	}
	return req
}

func TestExtractRealIPIgnoresUntrustedForwardedFor(t *testing.T) {
	c, _ := gin.CreateTestContext(nil)
	c.Request = newTestRequestWithRemote("8.8.8.8:12345", "127.0.0.1")

	got := extractRealIP(c, nil)
	if got != "8.8.8.8" {
		t.Fatalf("real IP = %q, want remote address", got)
	}
}

func TestExtractRealIPUsesTrustedProxyForwardedFor(t *testing.T) {
	c, _ := gin.CreateTestContext(nil)
	c.Request = newTestRequestWithRemote("127.0.0.1:12345", "8.8.8.8")

	got := extractRealIP(c, NewTrustedProxyMiddleware(nil).trustedProxies)
	if got != "8.8.8.8" {
		t.Fatalf("real IP = %q, want forwarded client", got)
	}
}
