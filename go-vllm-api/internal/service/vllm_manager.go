package service

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"go-vllm-api/internal/config"

	"go.uber.org/zap"
)

type VLLMManager struct {
	logger       *zap.Logger
	cfg          *config.VLLMConfig
	switchLock   sync.Mutex
	requestClient *http.Client
}

type ModelScanResult struct {
	Name         string `json:"name"`
	Path         string `json:"path"`
	EstimatedVRAM string `json:"estimated_vram"`
	SizeBytes    int64  `json:"size_bytes"`
}

func NewVLLMManager(cfg *config.VLLMConfig, logger *zap.Logger) *VLLMManager {
	return &VLLMManager{
		logger: logger,
		cfg:    cfg,
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
	cmd := exec.Command("systemctl", "restart", serviceName)
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("restart vllm service: %w", err)
	}
	vm.logger.Info("vllm service restarted", zap.String("model", modelName))

	time.Sleep(5 * time.Second)

	if err := vm.TestModel(ctx, port, modelName); err != nil {
		vm.logger.Warn("model test failed after switch", zap.String("model", modelName), zap.Error(err))
		return fmt.Errorf("model test failed: %w", err)
	}

	vm.logger.Info("model switched and verified", zap.String("model", modelName))
	return nil
}

func (vm *VLLMManager) TestModel(ctx context.Context, port int, modelName string) error {
	maxRetries := 5
	for attempt := 1; attempt <= maxRetries; attempt++ {
		vm.logger.Info("testing model", zap.String("model", modelName), zap.Int("attempt", attempt))
		err := vm.sendTestRequest(ctx, port, modelName)
		if err == nil {
			vm.logger.Info("model test passed", zap.String("model", modelName))
			return nil
		}
		vm.logger.Warn("model test attempt failed", zap.String("model", modelName), zap.Int("attempt", attempt), zap.Error(err))
		if attempt < maxRetries {
			time.Sleep(5 * time.Second)
		}
	}
	return fmt.Errorf("model %s failed after %d attempts", modelName, maxRetries)
}

func (vm *VLLMManager) sendTestRequest(ctx context.Context, port int, modelName string) error {
	url := fmt.Sprintf("http://localhost:%d/v1/chat/completions", port)
	payload := map[string]interface{}{
		"model":  modelName,
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
	cmd := exec.Command("systemctl", "is-active", serviceName)
	output, err := cmd.Output()
	status := "unknown"
	if err == nil {
		status = strings.TrimSpace(string(output))
	}
	return map[string]interface{}{
		"service_name": serviceName,
		"status":       status,
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
		"model":  modelName,
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
