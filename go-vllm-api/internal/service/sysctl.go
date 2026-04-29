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
	logger             *zap.Logger
	needsSudo          bool
	systemctlPath      string
	systemctlAvailable bool
	vllmPort           int
	mu                 sync.Mutex
}

func NewSystemController(logger *zap.Logger) *SystemController {
	sc := &SystemController{
		logger:   logger,
		vllmPort: 8000,
	}
	
	sc.systemctlPath, sc.systemctlAvailable = sc.detectSystemctl()
	sc.needsSudo = sc.checkSudo()
	
	if sc.systemctlAvailable {
		logger.Info("systemctl detected", zap.String("path", sc.systemctlPath), zap.Bool("needs_sudo", sc.needsSudo))
	} else {
		logger.Warn("systemctl not available, service operations will fail")
	}
	
	return sc
}

func (sc *SystemController) SetVLLMPort(port int) {
	sc.mu.Lock()
	defer sc.mu.Unlock()
	sc.vllmPort = port
}

func (sc *SystemController) checkSudo() bool {
	cmd := exec.Command("sudo", "-n", "true")
	if err := cmd.Run(); err != nil {
		return false
	}
	return true
}

func (sc *SystemController) detectSystemctl() (string, bool) {
	path, err := exec.LookPath("systemctl")
	if err != nil {
		sc.logger.Warn("systemctl not found in PATH", zap.Error(err))
		return "", false
	}
	return path, true
}

func (sc *SystemController) command(args ...string) *exec.Cmd {
	if len(args) == 0 {
		return nil
	}
	if args[0] == "systemctl" {
		if !sc.systemctlAvailable {
			return nil
		}
		args = append([]string{sc.systemctlPath}, args[1:]...)
	}
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
	if cmd == nil {
		sc.logger.Error("start service", zap.String("service", name), zap.String("reason", "systemctl unavailable"))
		return false
	}
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
	if cmd == nil {
		sc.logger.Error("stop service", zap.String("service", name), zap.String("reason", "systemctl unavailable"))
		return false
	}
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

	sc.clearModelPathEnv(name)

	cmd := sc.command("systemctl", "stop", name)
	if cmd == nil {
		sc.logger.Error("restart service", zap.String("service", name), zap.String("reason", "systemctl unavailable"))
		return false
	}
	if err := cmd.Run(); err != nil {
		sc.logger.Error("stop service before restart", zap.String("service", name), zap.Error(err))
		return false
	}

	waited := 0
	for waited < 30 {
		status := sc.getServiceStatusLocked(name)
		if status != "active" && status != "deactivating" {
			break
		}
		time.Sleep(1 * time.Second)
		waited++
	}

	if waited >= 30 {
		sc.logger.Warn("service stop timeout, forcing kill", zap.String("service", name))
		killCmd := sc.command("systemctl", "kill", name)
		if killCmd != nil {
			killCmd.Run()
			time.Sleep(2 * time.Second)
		}
	}

	cmd = sc.command("systemctl", "start", name)
	if cmd == nil {
		sc.logger.Error("restart service", zap.String("service", name), zap.String("reason", "systemctl unavailable"))
		return false
	}
	if err := cmd.Run(); err != nil {
		sc.logger.Error("restart service", zap.String("service", name), zap.Error(err))
		return false
	}
	sc.logger.Info("service restarted", zap.String("service", name))
	return true
}

func (sc *SystemController) clearModelPathEnv(name string) {
	cmd := sc.command("systemctl", "unset-environment", "VLLM_MODEL_PATH")
	if cmd != nil {
		if err := cmd.Run(); err != nil {
			sc.logger.Debug("clear VLLM_MODEL_PATH env failed", zap.Error(err))
		}
	}
}

func (sc *SystemController) getServiceStatusLocked(name string) string {
	cmd := sc.command("systemctl", "is-active", name)
	if cmd == nil {
		return "unavailable"
	}
	output, err := cmd.Output()
	if err != nil {
		return "inactive"
	}
	return strings.TrimSpace(string(output))
}

func (sc *SystemController) IsServiceRunning(name string) bool {
	sc.mu.Lock()
	defer sc.mu.Unlock()

	if sc.systemctlAvailable {
		cmd := sc.command("systemctl", "is-active", name)
		if cmd == nil {
			return false
		}
		output, err := cmd.Output()
		if err != nil {
			return false
		}
		return strings.TrimSpace(string(output)) == "active"
	}

	vllmPort := sc.vllmPort
	if name != "vllm-aiclient" {
		return false
	}

	addrs := []string{
		fmt.Sprintf("127.0.0.1:%d", vllmPort),
		fmt.Sprintf("localhost:%d", vllmPort),
	}
	for _, addr := range addrs {
		conn, err := net.DialTimeout("tcp", addr, 1*time.Second)
		if err == nil {
			conn.Close()
			sc.logger.Debug("service status via port check", zap.String("service", name), zap.String("addr", addr))
			return true
		}
	}
	return false
}

func (sc *SystemController) GetServiceStatus(name string) string {
	cmd := sc.command("systemctl", "is-active", name)
	if cmd == nil {
		return "unavailable"
	}
	output, err := cmd.Output()
	if err != nil {
		return "unknown"
	}
	return strings.TrimSpace(string(output))
}

func (sc *SystemController) GetServiceInfo(name string) map[string]string {
	cmd := sc.command("systemctl", "show", name, "--property=ActiveState,SubState,MainPID,MemoryCurrent")
	if cmd == nil {
		return map[string]string{"error": "systemctl unavailable"}
	}
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
