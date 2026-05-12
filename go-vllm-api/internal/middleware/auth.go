package middleware

import (
	"crypto/subtle"
	"net/http"
	"os"
	"strings"

	"go-vllm-api/internal/config"

	"github.com/gin-gonic/gin"
)

type AdminAuthMiddleware struct {
	enabled           bool
	tokens            []string
	protectedPrefixes []string
	exemptPaths       map[string]bool
}

func NewAdminAuthMiddleware(authCfg config.AuthConfig) *AdminAuthMiddleware {
	tokens := make([]string, 0)
	for _, envName := range []string{"AI_OS_ADMIN_TOKEN", "ADMIN_API_KEY", "AI_OS_API_KEY"} {
		tokens = append(tokens, splitCSV(os.Getenv(envName))...)
	}
	if authCfg.APIKey != "" {
		tokens = append(tokens, strings.TrimSpace(authCfg.APIKey))
	}
	for _, token := range authCfg.APIKeys {
		if strings.TrimSpace(token) != "" {
			tokens = append(tokens, strings.TrimSpace(token))
		}
	}
	tokens = uniqueStrings(tokens)

	enabled := authCfg.Enabled || len(tokens) > 0
	if envEnabled := os.Getenv("AI_OS_AUTH_ENABLED"); envEnabled != "" {
		enabled = strings.EqualFold(envEnabled, "true") || envEnabled == "1" || strings.EqualFold(envEnabled, "yes")
	}

	return &AdminAuthMiddleware{
		enabled:           enabled,
		tokens:            tokens,
		protectedPrefixes: []string{"/manage", "/ws"},
		exemptPaths: map[string]bool{
			"/health":          true,
			"/health/detailed": true,
			"/health/history":  true,
			"/metrics":         true,
		},
	}
}

func splitCSV(value string) []string {
	if value == "" {
		return nil
	}
	parts := strings.Split(value, ",")
	result := make([]string, 0, len(parts))
	for _, part := range parts {
		if trimmed := strings.TrimSpace(part); trimmed != "" {
			result = append(result, trimmed)
		}
	}
	return result
}

func uniqueStrings(values []string) []string {
	seen := map[string]bool{}
	result := make([]string, 0, len(values))
	for _, value := range values {
		if value == "" || seen[value] {
			continue
		}
		seen[value] = true
		result = append(result, value)
	}
	return result
}

func requestToken(c *gin.Context) string {
	auth := c.GetHeader("Authorization")
	if strings.HasPrefix(strings.ToLower(auth), "bearer ") {
		return strings.TrimSpace(auth[7:])
	}
	if apiKey := c.GetHeader("X-API-Key"); apiKey != "" {
		return strings.TrimSpace(apiKey)
	}
	return strings.TrimSpace(c.Query("api_key"))
}

func tokenAllowed(token string, allowed []string) bool {
	if token == "" {
		return false
	}
	for _, candidate := range allowed {
		if subtle.ConstantTimeCompare([]byte(token), []byte(candidate)) == 1 {
			return true
		}
	}
	return false
}

func (m *AdminAuthMiddleware) isProtectedPath(path string) bool {
	if m.exemptPaths[path] {
		return false
	}
	for _, prefix := range m.protectedPrefixes {
		if path == prefix || strings.HasPrefix(path, prefix+"/") {
			return true
		}
	}
	return false
}

func (m *AdminAuthMiddleware) Handler() gin.HandlerFunc {
	return func(c *gin.Context) {
		authenticated := tokenAllowed(requestToken(c), m.tokens)
		c.Set("authenticated", authenticated)
		c.Set("auth_enabled", m.enabled)

		if m.enabled && m.isProtectedPath(c.Request.URL.Path) && !authenticated {
			c.Header("WWW-Authenticate", "Bearer")
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "admin authentication required"})
			return
		}

		c.Next()
	}
}
