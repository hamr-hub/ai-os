package service

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"time"

	"go-vllm-api/internal/config"

	"go.uber.org/zap"
)

type VLLMManager struct {
	logger        *zap.Logger
	cfg           *config.VLLMConfig
	sysCtl        *SystemController
	switchLock    sync.Mutex
	requestClient *http.Client
	
	cachedPort     int
	portCachedAt   time.Time
	portMu         sync.RWMutex
}

type ModelScanResult struct {
	Name          string `json:"name"`
	Path          string `json:"path"`
	EstimatedVRAM string `json:"estimated_vram"`
	SizeBytes     int64  `json:"size_bytes"`
}

func NewVLLMManager(cfg *config.VLLMConfig, logger *zap.Logger, sysCtl *SystemController) *VLLMManager {
	return &VLLMManager{
		logger: logger,
		cfg:    cfg,
		sysCtl: sysCtl,
		requestClient: &http.Client{
			Timeout: 30 * time.Second,
			Transport: &http.Transport{
				MaxIdleConns:        10,
				MaxIdleConnsPerHost: 5,
				IdleConnTimeout:     30 * time.Second,
			},
		},
	}
}

func (vm *VLLMManager) SetConfig(cfg *config.VLLMConfig) {
	vm.cfg = cfg
}

func (vm *VLLMManager) SetSysCtl(sysCtl *SystemController) {
	vm.sysCtl = sysCtl
}

func (vm *VLLMManager) checkPort(port int, timeout time.Duration) bool {
	address := fmt.Sprintf("localhost:%d", port)
	conn, err := net.DialTimeout("tcp", address, timeout)
	if err != nil {
		return false
	}
	conn.Close()
	return true
}

func (vm *VLLMManager) DiscoverVLLMPort() int {
	vm.portMu.RLock()
	if vm.cachedPort != 0 && time.Since(vm.portCachedAt) < 5*time.Minute {
		port := vm.cachedPort
		vm.portMu.RUnlock()
		vm.logger.Debug("Using cached vLLM port", zap.Int("port", port))
		return port
	}
	vm.portMu.RUnlock()

	defaultPort := vm.cfg.DefaultPort
	if defaultPort == 0 {
		defaultPort = 8000
	}

	scriptPath := vm.cfg.StartScript
	if scriptPath == "" {
		scriptPath = "/root/ai-suite/start_vllm.sh"
	}
	serviceName := vm.cfg.ServiceName
	if serviceName == "" {
		serviceName = "vllm-aiclient"
	}

	content, err := os.ReadFile(scriptPath)
	if err == nil {
		lines := strings.Split(string(content), "\n")
		for _, line := range lines {
			if strings.Contains(line, "--port") {
				parts := strings.Fields(line)
				for i, part := range parts {
					if part == "--port" && i+1 < len(parts) {
						if port, err := strconv.Atoi(parts[i+1]); err == nil {
							if vm.checkPort(port, 2*time.Second) {
								vm.logger.Info("Discovered vLLM port from start script", zap.Int("port", port))
								vm.portMu.Lock()
								vm.cachedPort = port
								vm.portCachedAt = time.Now()
								vm.portMu.Unlock()
								return port
							}
						}
					}
				}
			}
		}
	}

	serviceFile := fmt.Sprintf("/etc/systemd/system/%s.service", serviceName)
	if content, err := os.ReadFile(serviceFile); err == nil {
		lines := strings.Split(string(content), "\n")
		for _, line := range lines {
			if strings.HasPrefix(line, "ExecStart=") {
				execLine := strings.TrimPrefix(line, "ExecStart=")
				if strings.Contains(execLine, "--port") {
					parts := strings.Fields(execLine)
					for i, part := range parts {
						if part == "--port" && i+1 < len(parts) {
							if port, err := strconv.Atoi(parts[i+1]); err == nil {
								if vm.checkPort(port, 2*time.Second) {
									vm.logger.Info("Discovered vLLM port from systemd service", zap.Int("port", port))
									vm.portMu.Lock()
									vm.cachedPort = port
									vm.portCachedAt = time.Now()
									vm.portMu.Unlock()
									return port
								}
							}
						}
					}
				}
			}
		}
	}

	scanPorts := []int{8000, 8001, 8002, 8003, 8004, 8005, 8006, 8007, 8008, 8009, 8010}
	for _, port := range scanPorts {
		if vm.checkPort(port, 2*time.Second) {
			healthURL := fmt.Sprintf("http://localhost:%d/health", port)
			req, err := http.NewRequest("GET", healthURL, nil)
			if err == nil {
				client := &http.Client{Timeout: 2 * time.Second}
				resp, err := client.Do(req)
				if err == nil {
					if resp.StatusCode == http.StatusOK {
						resp.Body.Close()
						vm.logger.Info("Discovered vLLM port by scanning", zap.Int("port", port))
						vm.portMu.Lock()
						vm.cachedPort = port
						vm.portCachedAt = time.Now()
						vm.portMu.Unlock()
						return port
					}
					resp.Body.Close()
				}
			}
		}
	}

	vm.logger.Warn("Failed to discover vLLM port, using default", zap.Int("default_port", defaultPort))
	vm.portMu.Lock()
	vm.cachedPort = defaultPort
	vm.portCachedAt = time.Now()
	vm.portMu.Unlock()
	return defaultPort
}

func (vm *VLLMManager) RefreshVLLMPortCache() {
	vm.portMu.Lock()
	vm.cachedPort = 0
	vm.portCachedAt = time.Time{}
	vm.portMu.Unlock()
	vm.logger.Info("vLLM port cache refreshed")
	vm.DiscoverVLLMPort()
}

func (vm *VLLMManager) ScanModels() []ModelScanResult {
	basePath := vm.cfg.ModelBasePath
	if basePath == "" {
		basePath = "/mnt/pve_models"
	}
	var results []ModelScanResult
	entries, err := os.ReadDir(basePath)
	if err != nil {
		vm.logger.Error("scan models directory", zap.String("path", basePath), zap.Error(err))
		return results
	}
	for _, entry := range entries {
		if !entry.IsDir() {
			continue
		}
		modelPath := filepath.Join(basePath, entry.Name())
		size := vm.estimateModelSize(modelPath)
		estVRAM := vm.formatVRAM(size)
		results = append(results, ModelScanResult{
			Name:          entry.Name(),
			Path:          modelPath,
			EstimatedVRAM: estVRAM,
			SizeBytes:     size,
		})
	}
	return results
}

func (vm *VLLMManager) estimateModelSize(modelPath string) int64 {
	var totalSize int64
	filepath.Walk(modelPath, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return nil
		}
		if !info.IsDir() {
			ext := strings.ToLower(filepath.Ext(path))
			if ext == ".safetensors" || ext == ".bin" || ext == ".gguf" || ext == ".pt" || ext == ".onnx" {
				totalSize += info.Size()
			}
		}
		return nil
	})
	return totalSize
}

func (vm *VLLMManager) formatVRAM(bytes int64) string {
	gb := float64(bytes) / float64(1<<30)
	return fmt.Sprintf("%.0fGB", gb*1.2)
}

func (vm *VLLMManager) SwitchModel(ctx context.Context, modelPath string) error {
	vm.switchLock.Lock()
	defer vm.switchLock.Unlock()

	scriptPath := vm.cfg.StartScript
	if scriptPath == "" {
		scriptPath = "/root/ai-suite/start_vllm.sh"
	}

	stateFile := filepath.Join(filepath.Dir(scriptPath), ".vllm_model_path")
	if err := os.WriteFile(stateFile, []byte(modelPath+"\n"), 0644); err == nil {
		vm.logger.Info("vllm model state updated", zap.String("path", modelPath), zap.String("state_file", stateFile))
		return nil
	} else {
		vm.logger.Warn("write model state file failed, falling back to start script update", zap.String("state_file", stateFile), zap.Error(err))
	}

	content, err := os.ReadFile(scriptPath)
	if err != nil {
		return fmt.Errorf("read start script: %w", err)
	}

	newContent := vm.replaceModelPath(string(content), modelPath)
	if newContent == string(content) {
		vm.logger.Info("model path unchanged", zap.String("path", modelPath))
		return nil
	}

	if err := os.WriteFile(scriptPath, []byte(newContent), 0755); err != nil {
		return fmt.Errorf("write start script: %w", err)
	}

	vm.logger.Info("start script updated", zap.String("path", modelPath))
	return nil
}

func (vm *VLLMManager) replaceModelPath(content string, newPath string) string {
	lines := strings.Split(content, "\n")
	modified := false
	for i, line := range lines {
		trimmed := strings.TrimSpace(line)
		if strings.Contains(trimmed, "--model") || strings.Contains(trimmed, "-m ") {
			if strings.HasPrefix(trimmed, "#") {
				continue
			}
			parts := strings.Fields(trimmed)
			for j, p := range parts {
				if p == "--model" && j+1 < len(parts) {
					oldPath := parts[j+1]
					if oldPath != newPath {
						parts[j+1] = newPath
						lines[i] = strings.Join(parts, " ")
						modified = true
					}
				}
			}
		}
	}
	if !modified {
		for i, line := range lines {
			if strings.Contains(line, "/mnt/pve_models/") && !strings.HasPrefix(strings.TrimSpace(line), "#") {
				parts := strings.Fields(line)
				for j, p := range parts {
					if strings.HasPrefix(p, "/mnt/pve_models/") {
						parts[j] = newPath
						lines[i] = strings.Join(parts, " ")
						modified = true
						break
					}
				}
				if modified {
					break
				}
			}
		}
	}
	return strings.Join(lines, "\n")
}

func (vm *VLLMManager) SwitchModelWithTest(ctx context.Context, modelPath string, modelName string, port int) error {
	if err := vm.SwitchModel(ctx, modelPath); err != nil {
		return err
	}

	serviceName := vm.cfg.ServiceName
	if serviceName == "" {
		serviceName = "vllm"
	}
	if vm.sysCtl == nil || !vm.sysCtl.RestartService(serviceName) {
		return fmt.Errorf("restart vllm service %s failed", serviceName)
	}
	vm.logger.Info("vllm service restarted", zap.String("model", modelName), zap.String("service", serviceName))

	// 600s timeout for large models (70B+) to load into VRAM
	if err := vm.WaitUntilReady(ctx, port, 600*time.Second, 5*time.Second); err != nil {
		return fmt.Errorf("wait for vllm readiness: %w", err)
	}

	if err := vm.TestModel(ctx, port, modelName); err != nil {
		vm.logger.Warn("model test failed after switch", zap.String("model", modelName), zap.Error(err))
		return fmt.Errorf("model test failed: %w", err)
	}

	vm.logger.Info("model switched and verified", zap.String("model", modelName))
	return nil
}

func (vm *VLLMManager) TestModel(ctx context.Context, port int, modelName string) error {
	maxRetries := 5
	retryInterval := 3 * time.Second
	for attempt := 1; attempt <= maxRetries; attempt++ {
		vm.logger.Info("testing model", zap.String("model", modelName), zap.Int("attempt", attempt))
		err := vm.sendTestRequest(ctx, port, modelName)
		if err == nil {
			vm.logger.Info("model test passed", zap.String("model", modelName))
			return nil
		}
		vm.logger.Warn("model test attempt failed", zap.String("model", modelName), zap.Int("attempt", attempt), zap.Error(err))
		if attempt < maxRetries {
			time.Sleep(retryInterval)
			retryInterval = min(retryInterval+2*time.Second, 5*time.Second)
		}
	}
	return fmt.Errorf("model %s failed after %d attempts", modelName, maxRetries)
}

func (vm *VLLMManager) sendTestRequest(ctx context.Context, port int, modelName string) error {
	url := fmt.Sprintf("http://localhost:%d/v1/chat/completions", port)
	payload := map[string]interface{}{
		"model": modelName,
		"messages": []map[string]interface{}{
			{"role": "user", "content": "Hello"},
		},
		"max_tokens": 5,
		"stream":     false,
	}

	data, err := json.Marshal(payload)
	if err != nil {
		return err
	}

	req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(data))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := vm.requestClient.Do(req)
	if err != nil {
		return fmt.Errorf("test request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("test returned %d: %s", resp.StatusCode, string(body))
	}

	var result map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return fmt.Errorf("decode response: %w", err)
	}

	if choices, ok := result["choices"].([]interface{}); ok && len(choices) > 0 {
		return nil
	}
	return fmt.Errorf("no choices in response")
}

func (vm *VLLMManager) WaitUntilReady(ctx context.Context, port int, timeout time.Duration, interval time.Duration) error {
	if timeout <= 0 {
		timeout = 600 * time.Second
	}
	if interval <= 0 {
		interval = 5 * time.Second
	}

	deadline := time.Now().Add(timeout)
	var lastErr error
	pollInterval := 2 * time.Second

	// Use a dedicated client for readiness checks with longer timeout
	readinessClient := &http.Client{
		Timeout: 10 * time.Second,
		Transport: &http.Transport{
			MaxIdleConns:        5,
			MaxIdleConnsPerHost: 2,
			IdleConnTimeout:     30 * time.Second,
		},
	}

	startTime := time.Now()
	attemptCount := 0
	for {
		attemptCount++
		req, err := http.NewRequestWithContext(ctx, "GET", fmt.Sprintf("http://localhost:%d/v1/models", port), nil)
		if err != nil {
			return err
		}

		resp, err := readinessClient.Do(req)
		if err == nil {
			body, readErr := io.ReadAll(io.LimitReader(resp.Body, 512))
			resp.Body.Close()
			if readErr != nil {
				lastErr = fmt.Errorf("read readiness response: %w", readErr)
			} else if resp.StatusCode == http.StatusOK {
				elapsed := time.Since(startTime)
				vm.logger.Info("vLLM model ready",
					zap.Int("port", port),
					zap.Duration("elapsed", elapsed),
					zap.Int("attempts", attemptCount))
				return nil
			} else {
				lastErr = fmt.Errorf("readiness returned %d: %s", resp.StatusCode, strings.TrimSpace(string(body)))
			}
		} else {
			lastErr = fmt.Errorf("readiness probe failed: %w", err)
		}

		if time.Now().After(deadline) {
			elapsed := time.Since(startTime)
			vm.logger.Warn("vLLM readiness timeout",
				zap.Int("port", port),
				zap.Duration("elapsed", elapsed),
				zap.Int("attempts", attemptCount),
				zap.Error(lastErr))
			if lastErr == nil {
				lastErr = fmt.Errorf("readiness probe timed out")
			}
			return lastErr
		}

		elapsed := time.Since(startTime)
		vm.logger.Info("waiting for vLLM readiness",
			zap.Int("port", port),
			zap.Duration("elapsed", elapsed),
			zap.Duration("remaining", deadline.Sub(time.Now())),
			zap.Int("attempt", attemptCount))

		timer := time.NewTimer(pollInterval)
		select {
		case <-ctx.Done():
			timer.Stop()
			return ctx.Err()
		case <-timer.C:
		}
		pollInterval = time.Duration(float64(pollInterval) * 1.5)
		if pollInterval > interval {
			pollInterval = interval
		}
	}
}

func (vm *VLLMManager) ReadStartScript() (string, error) {
	scriptPath := vm.cfg.StartScript
	if scriptPath == "" {
		return "", fmt.Errorf("start script path not configured")
	}
	content, err := os.ReadFile(scriptPath)
	if err != nil {
		return "", fmt.Errorf("read start script: %w", err)
	}
	return string(content), nil
}

func (vm *VLLMManager) GetVLLMServiceStatus() map[string]interface{} {
	serviceName := vm.cfg.ServiceName
	if serviceName == "" {
		serviceName = "vllm"
	}
	status := "unknown"
	info := map[string]string{}
	if vm.sysCtl != nil {
		status = vm.sysCtl.GetServiceStatus(serviceName)
		info = vm.sysCtl.GetServiceInfo(serviceName)
	}
	return map[string]interface{}{
		"service_name": serviceName,
		"status":       status,
		"info":         info,
	}
}

func (vm *VLLMManager) FlushKVCache(ctx context.Context, port int) error {
	url := fmt.Sprintf("http://localhost:%d/cache_admin", port)
	payload := map[string]interface{}{
		"action": "flush",
	}
	data, err := json.Marshal(payload)
	if err != nil {
		return err
	}
	req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(data))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := vm.requestClient.Do(req)
	if err != nil {
		return fmt.Errorf("flush kv cache: %w", err)
	}
	defer resp.Body.Close()
	return nil
}

func (vm *VLLMManager) StreamTestModel(ctx context.Context, port int, modelName string) error {
	url := fmt.Sprintf("http://localhost:%d/v1/chat/completions", port)
	payload := map[string]interface{}{
		"model": modelName,
		"messages": []map[string]interface{}{
			{"role": "user", "content": "Hello"},
		},
		"max_tokens": 20,
		"stream":     true,
	}

	data, err := json.Marshal(payload)
	if err != nil {
		return err
	}

	req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(data))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "text/event-stream")

	resp, err := vm.requestClient.Do(req)
	if err != nil {
		return fmt.Errorf("stream test request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("stream test returned %d", resp.StatusCode)
	}

	scanner := bufio.NewScanner(resp.Body)
	chunkCount := 0
	timeout := time.After(15 * time.Second)

	done := make(chan struct{})
	go func() {
		for scanner.Scan() {
			line := scanner.Text()
			if strings.HasPrefix(line, "data: ") {
				data := strings.TrimPrefix(line, "data: ")
				if data == "[DONE]" {
					break
				}
				chunkCount++
			}
		}
		close(done)
	}()

	select {
	case <-done:
		if chunkCount == 0 {
			return fmt.Errorf("no streaming chunks received")
		}
		return nil
	case <-timeout:
		if chunkCount > 0 {
			return nil
		}
		return fmt.Errorf("stream test timeout")
	}
}
