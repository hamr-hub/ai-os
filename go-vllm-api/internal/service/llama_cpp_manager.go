package service

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"time"

	"go.uber.org/zap"
)

type LlamaCppServerConfig struct {
	Port        int    `json:"port"`
	ModelPath   string `json:"model_path"`
	NGPULayers  int    `json:"n_gpu_layers"`
	CtxSize     int    `json:"ctx_size"`
	NThreads    int    `json:"n_threads"`
	Host        string `json:"host"`
	ExtraArgs   []string `json:"extra_args"`
}

type LlamaCppProcessInfo struct {
	ModelName   string    `json:"model_name"`
	Port        int       `json:"port"`
	PID         int       `json:"pid"`
	Running     bool      `json:"running"`
	StartedAt   time.Time `json:"started_at"`
	Config      LlamaCppServerConfig `json:"config"`
}

type GGUFModelInfo struct {
	Name     string `json:"name"`
	Path     string `json:"path"`
	SizeBytes int64 `json:"size_bytes"`
	SizeStr  string `json:"size"`
}

type LlamaCppManager struct {
	logger        *zap.Logger
	processes     map[string]*llamaCppProcess
	mu            sync.Mutex
	requestClient *http.Client
	modelsBasePath string
	defaultNGPULayers int
	defaultCtxSize    int
	defaultHost       string
	serverModule      string
}

type llamaCppProcess struct {
	cmd    *exec.Cmd
	config LlamaCppServerConfig
	pid    int
	started time.Time
}

func NewLlamaCppManager(logger *zap.Logger) *LlamaCppManager {
	return &LlamaCppManager{
		logger:        logger,
		processes:     make(map[string]*llamaCppProcess),
		modelsBasePath: "/mnt/pve_models",
		defaultNGPULayers: -1,
		defaultCtxSize:    4096,
		defaultHost:       "0.0.0.0",
		serverModule:      "llama_cpp.server",
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

func (lm *LlamaCppManager) SetDefaults(basePath string, nGPULayers int, ctxSize int, host string, serverModule string) {
	if basePath != "" {
		lm.modelsBasePath = basePath
	}
	if nGPULayers != 0 {
		lm.defaultNGPULayers = nGPULayers
	}
	if ctxSize != 0 {
		lm.defaultCtxSize = ctxSize
	}
	if host != "" {
		lm.defaultHost = host
	}
	if serverModule != "" {
		lm.serverModule = serverModule
	}
}

func (lm *LlamaCppManager) StartServer(ctx context.Context, modelName string, cfg LlamaCppServerConfig) error {
	lm.mu.Lock()
	if proc, exists := lm.processes[modelName]; exists && proc.cmd.ProcessState == nil {
		lm.mu.Unlock()
		return fmt.Errorf("server for %s already running", modelName)
	}

	nThreads := cfg.NThreads
	if nThreads <= 0 {
		nThreads = runtime.NumCPU()
	}

	args := []string{
		"-m", "llama_cpp.server",
		"--model", cfg.ModelPath,
		"--port", fmt.Sprintf("%d", cfg.Port),
		"--n_gpu_layers", fmt.Sprintf("%d", cfg.NGPULayers),
		"--ctx_size", fmt.Sprintf("%d", cfg.CtxSize),
		"--n_threads", fmt.Sprintf("%d", nThreads),
		"--host", cfg.Host,
	}
	args = append(args, cfg.ExtraArgs...)

	cmd := exec.CommandContext(ctx, "python", args...)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr

	if err := cmd.Start(); err != nil {
		lm.mu.Unlock()
		return fmt.Errorf("start llama_cpp server: %w", err)
	}

	proc := &llamaCppProcess{
		cmd:    cmd,
		config: cfg,
		pid:    cmd.Process.Pid,
		started: time.Now(),
	}
	lm.processes[modelName] = proc
	lm.mu.Unlock()

	lm.logger.Info("llama_cpp server started",
		zap.String("model", modelName),
		zap.Int("port", cfg.Port),
		zap.Int("pid", cmd.Process.Pid))

	go func() {
		err := cmd.Wait()
		lm.mu.Lock()
		delete(lm.processes, modelName)
		lm.mu.Unlock()
		if err != nil && err.Error() != "signal: killed" {
			lm.logger.Warn("llama_cpp server exited",
				zap.String("model", modelName),
				zap.Error(err))
		}
	}()

	return nil
}

func (lm *LlamaCppManager) StopServer(modelName string) error {
	lm.mu.Lock()
	proc, exists := lm.processes[modelName]
	if !exists {
		lm.mu.Unlock()
		return fmt.Errorf("no running server for %s", modelName)
	}
	lm.mu.Unlock()

	if proc.cmd.Process != nil {
		proc.cmd.Process.Signal(os.Interrupt)
		time.Sleep(2 * time.Second)

		done := make(chan error, 1)
		go func() {
			done <- proc.cmd.Wait()
		}()

		select {
		case <-done:
		case <-time.After(5 * time.Second):
			proc.cmd.Process.Kill()
		}
	}

	lm.mu.Lock()
	delete(lm.processes, modelName)
	lm.mu.Unlock()

	lm.logger.Info("llama_cpp server stopped", zap.String("model", modelName))
	return nil
}

func (lm *LlamaCppManager) IsServerRunning(modelName string) bool {
	lm.mu.Lock()
	defer lm.mu.Unlock()
	proc, exists := lm.processes[modelName]
	if !exists {
		return false
	}
	if proc.cmd.ProcessState != nil {
		return false
	}
	return true
}

func (lm *LlamaCppManager) GetServerStatus() map[string]LlamaCppProcessInfo {
	lm.mu.Lock()
	defer lm.mu.Unlock()

	status := make(map[string]LlamaCppProcessInfo)
	for name, proc := range lm.processes {
		running := proc.cmd.ProcessState == nil
		pid := 0
		if proc.cmd.Process != nil {
			pid = proc.cmd.Process.Pid
		}
		status[name] = LlamaCppProcessInfo{
			ModelName:  name,
			Port:       proc.config.Port,
			PID:        pid,
			Running:    running,
			StartedAt:  proc.started,
			Config:     proc.config,
		}
	}
	return status
}

func (lm *LlamaCppManager) GetServerPort(modelName string) int {
	lm.mu.Lock()
	defer lm.mu.Unlock()
	if proc, ok := lm.processes[modelName]; ok {
		return proc.config.Port
	}
	return 0
}

func (lm *LlamaCppManager) ScanGGUFModels() []GGUFModelInfo {
	var models []GGUFModelInfo
	basePath := lm.modelsBasePath

	entries, err := os.ReadDir(basePath)
	if err != nil {
		lm.logger.Error("scan gguf models", zap.String("path", basePath), zap.Error(err))
		return models
	}

	for _, entry := range entries {
		if !entry.IsDir() {
			continue
		}
		dirPath := filepath.Join(basePath, entry.Name())
		filepath.Walk(dirPath, func(path string, info os.FileInfo, err error) error {
			if err != nil {
				return nil
			}
			if !info.IsDir() && strings.HasSuffix(strings.ToLower(info.Name()), ".gguf") {
				sizeStr := formatFileSize(info.Size())
				models = append(models, GGUFModelInfo{
					Name:      info.Name(),
					Path:      path,
					SizeBytes: info.Size(),
					SizeStr:   sizeStr,
				})
			}
			return nil
		})
	}
	return models
}

func (lm *LlamaCppManager) TestModel(ctx context.Context, port int, modelPath string) error {
	maxRetries := 5
	for attempt := 1; attempt <= maxRetries; attempt++ {
		lm.logger.Info("testing llama_cpp model",
			zap.String("path", modelPath),
			zap.Int("port", port),
			zap.Int("attempt", attempt))

		err := lm.sendTestRequest(ctx, port, modelPath)
		if err == nil {
			lm.logger.Info("llama_cpp model test passed", zap.String("path", modelPath))
			return nil
		}

		lm.logger.Warn("llama_cpp model test attempt failed",
			zap.Int("attempt", attempt), zap.Error(err))
		if attempt < maxRetries {
			time.Sleep(3 * time.Second)
		}
	}
	return fmt.Errorf("llama_cpp model at port %d failed after %d attempts", port, maxRetries)
}

func (lm *LlamaCppManager) sendTestRequest(ctx context.Context, port int, modelPath string) error {
	url := fmt.Sprintf("http://localhost:%d/v1/chat/completions", port)
	payload := map[string]interface{}{
		"model":   modelPath,
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

	resp, err := lm.requestClient.Do(req)
	if err != nil {
		return fmt.Errorf("test request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("test returned %d: %s", resp.StatusCode, string(body))
	}
	return nil
}

func (lm *LlamaCppManager) CleanupAll() {
	lm.mu.Lock()
	models := make([]string, 0, len(lm.processes))
	for name := range lm.processes {
		models = append(models, name)
	}
	lm.mu.Unlock()

	for _, name := range models {
		lm.StopServer(name)
	}
	lm.logger.Info("all llama_cpp servers cleaned up")
}

func formatFileSize(bytes int64) string {
	if bytes >= 1<<30 {
		return fmt.Sprintf("%.1f GB", float64(bytes)/float64(1<<30))
	}
	if bytes >= 1<<20 {
		return fmt.Sprintf("%.1f MB", float64(bytes)/float64(1<<20))
	}
	return fmt.Sprintf("%d KB", bytes/1024)
}
