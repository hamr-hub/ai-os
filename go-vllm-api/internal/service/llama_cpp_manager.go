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

	"go-vllm-api/internal/config"

	"go.uber.org/zap"
)

type LlamaCppServerConfig struct {
	Port        int      `json:"port" yaml:"port"`
	ModelPath   string   `json:"model_path" yaml:"model_path"`
	NGPULayers  int      `json:"n_gpu_layers" yaml:"n_gpu_layers"`
	CtxSize     int      `json:"ctx_size" yaml:"ctx_size"`
	NThreads    int      `json:"n_threads" yaml:"n_threads"`
	Host        string   `json:"host" yaml:"host"`
	ExtraArgs   []string `json:"extra_args" yaml:"extra_args"`
}

type LlamaCppProcessInfo struct {
	ModelName string            `json:"model_name"`
	Port      int               `json:"port"`
	PID       int               `json:"pid"`
	Running   bool              `json:"running"`
	StartedAt time.Time         `json:"started_at"`
	Service   string            `json:"service"`
	Config    LlamaCppServerConfig `json:"config"`
}

type GGUFModelInfo struct {
	Name      string `json:"name"`
	Path      string `json:"path"`
	GGUFFile  string `json:"gguf_file,omitempty"`
	SizeBytes int64  `json:"size_bytes"`
	SizeStr   string `json:"size"`
	SizeMB    int    `json:"size_mb"`
}

type LlamaCppManager struct {
	logger           *zap.Logger
	processes        map[string]*llamaCppProcess
	modelConfigs     map[string]*LlamaCppServerConfig
	portByModel      map[string]int
	modelByPort      map[int]string
	processesByPort  map[int]*llamaCppProcess
	mu               sync.Mutex
	requestClient    *http.Client
	cfg              *config.AppConfig
}

type llamaCppProcess struct {
	cmd       *exec.Cmd
	config    LlamaCppServerConfig
	pid       int
	started   time.Time
	modelName string
}

func NewLlamaCppManager(logger *zap.Logger, cfg *config.AppConfig) *LlamaCppManager {
	return &LlamaCppManager{
		logger:          logger,
		processes:       make(map[string]*llamaCppProcess),
		modelConfigs:    make(map[string]*LlamaCppServerConfig),
		portByModel:     make(map[string]int),
		modelByPort:     make(map[int]string),
		processesByPort: make(map[int]*llamaCppProcess),
		requestClient: &http.Client{
			Timeout: 30 * time.Second,
			Transport: &http.Transport{
				MaxIdleConns:        10,
				MaxIdleConnsPerHost: 5,
				IdleConnTimeout:     30 * time.Second,
			},
		},
		cfg: cfg,
	}
}

func (lm *LlamaCppManager) RegisterModelsFromConfig(cfg *config.AppConfig) {
	lm.mu.Lock()
	defer lm.mu.Unlock()

	lm.cfg = cfg
	for name, mc := range cfg.Models {
		if mc.Service == "llama_cpp" {
			llamaCfg := &LlamaCppServerConfig{
				Port:       mc.Port,
				ModelPath:  mc.ModelPath,
				NGPULayers: mc.NGPULayers,
				CtxSize:    mc.CtxSize,
				NThreads:   mc.NThreads,
				Host:       mc.Host,
				ExtraArgs:  mc.ExtraArgs,
			}
			if llamaCfg.NGPULayers == 0 {
				llamaCfg.NGPULayers = cfg.LlamaCpp.DefaultNGPULayers
			}
			if llamaCfg.CtxSize == 0 {
				llamaCfg.CtxSize = cfg.LlamaCpp.DefaultCtxSize
			}
			if llamaCfg.Host == "" {
				llamaCfg.Host = cfg.LlamaCpp.DefaultHost
			}
			if llamaCfg.ModelPath == "" {
				llamaCfg.ModelPath = filepath.Join(cfg.LlamaCpp.ModelsBasePath, name)
			}
			lm.modelConfigs[name] = llamaCfg
			lm.portByModel[name] = mc.Port
			lm.modelByPort[mc.Port] = name
		}
	}
	lm.logger.Info("registered llama_cpp models from config", zap.Int("count", len(lm.modelConfigs)))
}

func (lm *LlamaCppManager) RegisterModel(modelName string, cfg LlamaCppServerConfig) {
	lm.mu.Lock()
	defer lm.mu.Unlock()
	lm.modelConfigs[modelName] = &cfg
	lm.portByModel[modelName] = cfg.Port
	lm.modelByPort[cfg.Port] = modelName
}

func (lm *LlamaCppManager) UnregisterModel(modelName string) {
	lm.mu.Lock()
	defer lm.mu.Unlock()
	if cfg, ok := lm.modelConfigs[modelName]; ok {
		port := cfg.Port
		lm.portByModel[modelName] = 0
		lm.modelByPort[port] = ""
		delete(lm.modelConfigs, modelName)
	}
}

func (lm *LlamaCppManager) GetModelPort(modelName string) int {
	lm.mu.Lock()
	defer lm.mu.Unlock()
	if port, ok := lm.portByModel[modelName]; ok {
		return port
	}
	return 0
}

func (lm *LlamaCppManager) GetModelByPort(port int) string {
	lm.mu.Lock()
	defer lm.mu.Unlock()
	if name, ok := lm.modelByPort[port]; ok {
		return name
	}
	return ""
}

func (lm *LlamaCppManager) StartServerByName(ctx context.Context, modelName string) error {
	lm.mu.Lock()
	serverCfg, ok := lm.modelConfigs[modelName]
	if !ok {
		lm.mu.Unlock()
		return fmt.Errorf("no config registered for model: %s", modelName)
	}

	if proc, exists := lm.processes[modelName]; exists && proc.cmd.ProcessState == nil {
		lm.mu.Unlock()
		return fmt.Errorf("server for %s already running on port %d", modelName, serverCfg.Port)
	}

	cfg := *serverCfg
	lm.mu.Unlock()

	return lm.StartServer(ctx, modelName, cfg)
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

	serverModule := lm.cfg.LlamaCpp.ServerModule
	if serverModule == "" {
		serverModule = "llama_cpp.server"
	}

	args := []string{
		"-m", serverModule,
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
		cmd:       cmd,
		config:    cfg,
		pid:       cmd.Process.Pid,
		started:   time.Now(),
		modelName: modelName,
	}
	lm.processes[modelName] = proc
	lm.processesByPort[cfg.Port] = proc
	lm.mu.Unlock()

	lm.logger.Info("llama_cpp server started",
		zap.String("model", modelName),
		zap.Int("port", cfg.Port),
		zap.Int("pid", cmd.Process.Pid))

	go func() {
		err := cmd.Wait()
		lm.mu.Lock()
		delete(lm.processes, modelName)
		delete(lm.processesByPort, cfg.Port)
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
	port := proc.config.Port
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
	delete(lm.processesByPort, port)
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
			ModelName: name,
			Port:      proc.config.Port,
			PID:       pid,
			Running:   running,
			StartedAt: proc.started,
			Service:   "llama_cpp",
			Config:    proc.config,
		}
	}
	return status
}

func (lm *LlamaCppManager) GetModelStatus(modelName string) LlamaCppProcessInfo {
	lm.mu.Lock()
	defer lm.mu.Unlock()

	port := lm.portByModel[modelName]
	running := lm.IsServerRunning(modelName)
	proc := lm.processes[modelName]
	pid := 0
	if proc != nil && proc.cmd.Process != nil && running {
		pid = proc.cmd.Process.Pid
	}

	cfg := LlamaCppServerConfig{}
	if mc, ok := lm.modelConfigs[modelName]; ok {
		cfg = *mc
	}

	return LlamaCppProcessInfo{
		ModelName: modelName,
		Port:      port,
		PID:       pid,
		Running:   running,
		Service:   "llama_cpp",
		Config:    cfg,
	}
}

func (lm *LlamaCppManager) GetAllRunningModels() []string {
	lm.mu.Lock()
	defer lm.mu.Unlock()
	var running []string
	for name := range lm.modelConfigs {
		if lm.IsServerRunning(name) {
			running = append(running, name)
		}
	}
	return running
}

func (lm *LlamaCppManager) ScanGGUFModels() []GGUFModelInfo {
	var models []GGUFModelInfo
	basePath := lm.cfg.LlamaCpp.ModelsBasePath

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
				sizeMB := int(info.Size() / (1024 * 1024))
				models = append(models, GGUFModelInfo{
					Name:      entry.Name(),
					Path:      dirPath,
					GGUFFile:  info.Name(),
					SizeBytes: info.Size(),
					SizeStr:   sizeStr,
					SizeMB:    sizeMB,
				})
			}
			return nil
		})
	}
	return models
}

type LlamaCppTestResult struct {
	Success        bool   `json:"success"`
	Message        string `json:"message"`
	Attempt        int    `json:"attempt"`
	ResponseContent string `json:"response_content,omitempty"`
	Error          string `json:"error,omitempty"`
}

func (lm *LlamaCppManager) TestModel(ctx context.Context, port int, modelName string) *LlamaCppTestResult {
	maxRetries := 5
	for attempt := 1; attempt <= maxRetries; attempt++ {
		lm.logger.Info("testing llama_cpp model",
			zap.String("model", modelName),
			zap.Int("port", port),
			zap.Int("attempt", attempt))

		result := lm.sendTestRequest(ctx, port, modelName)
		if result.Success {
			lm.logger.Info("llama_cpp model test passed", zap.String("model", modelName))
			return result
		}

		lm.logger.Warn("llama_cpp model test attempt failed",
			zap.Int("attempt", attempt), zap.String("message", result.Message))
		if attempt < maxRetries {
			time.Sleep(5 * time.Second)
		}
	}
	return &LlamaCppTestResult{
		Success: false,
		Message: fmt.Sprintf("llama_cpp model at port %d failed after %d attempts", port, maxRetries),
		Attempt: maxRetries,
	}
}

func (lm *LlamaCppManager) sendTestRequest(ctx context.Context, port int, modelName string) *LlamaCppTestResult {
	url := fmt.Sprintf("http://localhost:%d/v1/chat/completions", port)
	payload := map[string]interface{}{
		"model":   modelName,
		"messages": []map[string]interface{}{
			{"role": "user", "content": "Hello, please respond briefly."},
		},
		"max_tokens":  10,
		"temperature": 0.7,
		"stream":      false,
	}

	data, err := json.Marshal(payload)
	if err != nil {
		return &LlamaCppTestResult{Success: false, Message: fmt.Sprintf("marshal payload: %v", err), Attempt: 1}
	}

	req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(data))
	if err != nil {
		return &LlamaCppTestResult{Success: false, Message: fmt.Sprintf("create request: %v", err), Attempt: 1}
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := lm.requestClient.Do(req)
	if err != nil {
		return &LlamaCppTestResult{Success: false, Message: fmt.Sprintf("test request: %v", err), Attempt: 1, Error: err.Error()}
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return &LlamaCppTestResult{
			Success: false,
			Message: fmt.Sprintf("HTTP error %d: %s", resp.StatusCode, string(body)),
			Attempt: 1,
		}
	}

	var result map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return &LlamaCppTestResult{Success: false, Message: fmt.Sprintf("decode response: %v", err), Attempt: 1}
	}

	choices, ok := result["choices"].([]interface{})
	if !ok || len(choices) == 0 {
		return &LlamaCppTestResult{Success: false, Message: "invalid response structure: no choices", Attempt: 1}
	}

	choice, ok := choices[0].(map[string]interface{})
	if !ok {
		return &LlamaCppTestResult{Success: false, Message: "invalid response structure: choice format", Attempt: 1}
	}

	msg, ok := choice["message"].(map[string]interface{})
	if !ok {
		return &LlamaCppTestResult{Success: false, Message: "invalid response structure: no message", Attempt: 1}
	}

	content, _ := msg["content"].(string)
	if content == "" {
		return &LlamaCppTestResult{Success: false, Message: "Model returned empty response", Attempt: 1}
	}

	return &LlamaCppTestResult{
		Success:         true,
		Message:         "Model test passed",
		ResponseContent: strings.TrimSpace(content),
	}
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
