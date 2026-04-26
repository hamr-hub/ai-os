package service

import (
	"context"
	"fmt"
	"net"
	"os/exec"
	"strings"
	"sync"
	"time"

	"go.uber.org/zap"
)

type SystemController struct {
	logger     *zap.Logger
	needsSudo  bool
	mu         sync.Mutex
}

func NewSystemController(logger *zap.Logger) *SystemController {
	sc := &SystemController{logger: logger}
	sc.needsSudo = sc.checkSudo()
	return sc
}

func (sc *SystemController) checkSudo() bool {
	cmd := exec.Command("sudo", "-n", "true")
	if err := cmd.Run(); err != nil {
		return false
	}
	return true
}

func (sc *SystemController) command(args ...string) *exec.Cmd {
	if sc.needsSudo {
		allArgs := append([]string{"sudo"}, args...)
		return exec.Command(allArgs[0], allArgs[1:]...)
	}
	return exec.Command(args[0], args[1:]...)
}

func (sc *SystemController) StartService(name string) bool {
	sc.mu.Lock()
	defer sc.mu.Unlock()
	cmd := sc.command("systemctl", "start", name)
	if err := cmd.Run(); err != nil {
		sc.logger.Error("start service", zap.String("service", name), zap.Error(err))
		return false
	}
	sc.logger.Info("service started", zap.String("service", name))
	return true
}

func (sc *SystemController) StopService(name string) bool {
	sc.mu.Lock()
	defer sc.mu.Unlock()
	cmd := sc.command("systemctl", "stop", name)
	if err := cmd.Run(); err != nil {
		sc.logger.Error("stop service", zap.String("service", name), zap.Error(err))
		return false
	}
	sc.logger.Info("service stopped", zap.String("service", name))
	return true
}

func (sc *SystemController) RestartService(name string) bool {
	sc.mu.Lock()
	defer sc.mu.Unlock()
	cmd := sc.command("systemctl", "restart", name)
	if err := cmd.Run(); err != nil {
		sc.logger.Error("restart service", zap.String("service", name), zap.Error(err))
		return false
	}
	sc.logger.Info("service restarted", zap.String("service", name))
	return true
}

func (sc *SystemController) IsServiceRunning(name string) bool {
	cmd := sc.command("systemctl", "is-active", name)
	output, err := cmd.Output()
	if err != nil {
		return false
	}
	return strings.TrimSpace(string(output)) == "active"
}

func (sc *SystemController) GetServiceStatus(name string) string {
	cmd := sc.command("systemctl", "is-active", name)
	output, err := cmd.Output()
	if err != nil {
		return "unknown"
	}
	return strings.TrimSpace(string(output))
}

func (sc *SystemController) GetServiceInfo(name string) map[string]string {
	cmd := sc.command("systemctl", "show", name, "--property=ActiveState,SubState,MainPID,MemoryCurrent")
	output, err := cmd.Output()
	if err != nil {
		return map[string]string{"error": err.Error()}
	}
	info := map[string]string{}
	for _, line := range strings.Split(string(output), "\n") {
		if parts := strings.SplitN(line, "=", 2); len(parts) == 2 {
			info[parts[0]] = parts[1]
		}
	}
	return info
}

func (sc *SystemController) GetProcessInfo(port int) bool {
	addresses := []string{
		fmt.Sprintf("127.0.0.1:%d", port),
		fmt.Sprintf("localhost:%d", port),
	}

	for _, addr := range addresses {
		conn, err := net.DialTimeout("tcp", addr, 500*time.Millisecond)
		if err == nil {
			conn.Close()
			return true
		}
	}

	return false
}

func (sc *SystemController) StartWatchdog(ctx context.Context, serviceName string, interval time.Duration, maxAttempts int, cooldown time.Duration) {
	go func() {
		attempts := 0
		for {
			select {
			case <-ctx.Done():
				return
			case <-time.After(interval):
				if !sc.IsServiceRunning(serviceName) {
					attempts++
					if attempts > maxAttempts {
						sc.logger.Error("watchdog max attempts reached",
							zap.String("service", serviceName),
							zap.Int("attempts", attempts))
						return
					}
					sc.logger.Warn("service not running, restarting",
						zap.String("service", serviceName),
						zap.Int("attempt", attempts))
					sc.StartService(serviceName)
					time.Sleep(cooldown)
				} else {
					attempts = 0
				}
			}
		}
	}()
}
