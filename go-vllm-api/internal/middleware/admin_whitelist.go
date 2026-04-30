package middleware

import (
	"net"
	"net/http"

	"github.com/gin-gonic/gin"
)

var defaultAllowNets = []net.IPNet{
	parseCIDRNet("127.0.0.0/8"),
	parseCIDRNet("10.0.0.0/8"),
	parseCIDRNet("172.16.0.0/12"),
	parseCIDRNet("192.168.0.0/16"),
	parseCIDRNet("::1/128"),
	parseCIDRNet("fc00::/7"),
}

func parseCIDRNet(s string) net.IPNet {
	_, ipNet, _ := net.ParseCIDR(s)
	return *ipNet
}

type AdminWhitelistMiddleware struct {
	allowNets []net.IPNet
	allowIPs  []net.IP
	readOnly  map[string]bool
}

func NewAdminWhitelistMiddleware(extraCIDRs []string, readOnlyMethods []string) *AdminWhitelistMiddleware {
	nets := make([]net.IPNet, len(defaultAllowNets))
	copy(nets, defaultAllowNets)
	for _, cidr := range extraCIDRs {
		if _, ipNet, err := net.ParseCIDR(cidr); err == nil {
			nets = append(nets, *ipNet)
		} else {
			if ip := net.ParseIP(cidr); ip != nil {
				mask := ip.DefaultMask()
				if mask != nil {
					ipNet := net.IPNet{IP: ip.Mask(mask), Mask: mask}
					nets = append(nets, ipNet)
				}
			}
		}
	}

	rom := map[string]bool{}
	for _, m := range readOnlyMethods {
		rom[m] = true
	}
	if len(rom) == 0 {
		rom = map[string]bool{"GET": true, "HEAD": true}
	}

	return &AdminWhitelistMiddleware{
		allowNets: nets,
		readOnly:  rom,
	}
}

func (m *AdminWhitelistMiddleware) isAllowedIP(ip net.IP) bool {
	if ip.IsLoopback() {
		return true
	}
	for _, ipNet := range m.allowNets {
		if ipNet.Contains(ip) {
			return true
		}
	}
	return false
}

func (m *AdminWhitelistMiddleware) Handler() gin.HandlerFunc {
	return func(c *gin.Context) {
		clientIP := GetRealClientIP(c)
		ip := net.ParseIP(clientIP)
		if ip == nil {
			host, _, err := net.SplitHostPort(clientIP)
			if err == nil {
				ip = net.ParseIP(host)
			}
		}

		if ip != nil && m.isAllowedIP(ip) {
			c.Next()
			return
		}

		if m.readOnly[c.Request.Method] {
			c.Next()
			return
		}

		c.AbortWithStatusJSON(http.StatusForbidden, gin.H{
			"error": "admin write operations require internal network access",
			"client_ip": clientIP,
		})
	}
}
