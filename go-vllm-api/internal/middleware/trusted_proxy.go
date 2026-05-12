package middleware

import (
	"net"
	"strings"

	"github.com/gin-gonic/gin"
)

func parseCIDR(s string) *net.IPNet {
	_, ipNet, _ := net.ParseCIDR(s)
	return ipNet
}

type TrustedProxyMiddleware struct {
	trustedProxies []*net.IPNet
}

func NewTrustedProxyMiddleware(trustedProxyCIDRs []string) *TrustedProxyMiddleware {
	nets := []*net.IPNet{
		parseCIDR("127.0.0.0/8"),
		parseCIDR("::1/128"),
	}
	for _, cidr := range trustedProxyCIDRs {
		if strings.Contains(cidr, "/") {
			_, ipNet, err := net.ParseCIDR(cidr)
			if err == nil {
				nets = append(nets, ipNet)
			}
		} else {
			ip := net.ParseIP(cidr)
			if ip != nil {
				if ip.To4() != nil {
					_, ipNet, _ := net.ParseCIDR(cidr + "/32")
					nets = append(nets, ipNet)
				} else {
					_, ipNet, _ := net.ParseCIDR(cidr + "/128")
					nets = append(nets, ipNet)
				}
			}
		}
	}
	return &TrustedProxyMiddleware{trustedProxies: nets}
}

func (m *TrustedProxyMiddleware) Handler() gin.HandlerFunc {
	return func(c *gin.Context) {
		realIP := extractRealIP(c, m.trustedProxies)
		c.Set("real_client_ip", realIP)
		c.Next()
	}
}

func extractRealIP(c *gin.Context, trustedProxies []*net.IPNet) string {
	remoteIP := net.ParseIP(c.Request.RemoteAddr)
	if remoteIP == nil {
		host, _, err := net.SplitHostPort(c.Request.RemoteAddr)
		if err == nil {
			remoteIP = net.ParseIP(host)
		}
	}

	if remoteIP == nil {
		return c.ClientIP()
	}

	isTrusted := false
	for _, ipNet := range trustedProxies {
		if ipNet.Contains(remoteIP) {
			isTrusted = true
			break
		}
	}

	if !isTrusted {
		return remoteIP.String()
	}

	xff := c.GetHeader("X-Forwarded-For")
	if xff == "" {
		return remoteIP.String()
	}

	ips := strings.Split(xff, ",")
	for i := len(ips) - 1; i >= 0; i-- {
		ipStr := strings.TrimSpace(ips[i])
		ip := net.ParseIP(ipStr)
		if ip == nil {
			continue
		}
		proxyTrusted := false
		for _, ipNet := range trustedProxies {
			if ipNet.Contains(ip) {
				proxyTrusted = true
				break
			}
		}
		if !proxyTrusted {
			return ipStr
		}
	}

	if len(ips) > 0 {
		return strings.TrimSpace(ips[0])
	}

	return remoteIP.String()
}

func GetRealClientIP(c *gin.Context) string {
	if ip, exists := c.Get("real_client_ip"); exists {
		return ip.(string)
	}
	return c.ClientIP()
}
