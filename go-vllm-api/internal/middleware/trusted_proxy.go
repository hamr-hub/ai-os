package middleware

import (
	"net"
	"strings"

	"github.com/gin-gonic/gin"
)

var privateIPNets []*net.IPNet

func init() {
	privateIPNets = []*net.IPNet{
		parseCIDR("10.0.0.0/8"),
		parseCIDR("172.16.0.0/12"),
		parseCIDR("192.168.0.0/16"),
		parseCIDR("127.0.0.0/8"),
		parseCIDR("169.254.0.0/16"),
		parseCIDR("::1/128"),
		parseCIDR("fc00::/7"),
		parseCIDR("fe80::/10"),
	}
}

func parseCIDR(s string) *net.IPNet {
	_, ipNet, _ := net.ParseCIDR(s)
	return ipNet
}

func isPrivateIP(ip net.IP) bool {
	for _, ipNet := range privateIPNets {
		if ipNet.Contains(ip) {
			return true
		}
	}
	return false
}

type TrustedProxyMiddleware struct {
	trustedProxies []*net.IPNet
}

func NewTrustedProxyMiddleware(trustedProxyCIDRs []string) *TrustedProxyMiddleware {
	nets := make([]*net.IPNet, 0, len(trustedProxyCIDRs))
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

	if !isTrusted && !isPrivateIP(remoteIP) {
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
		if !proxyTrusted && !isPrivateIP(ip) {
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
