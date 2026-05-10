package service

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"time"

	"go-vllm-api/internal/config"
	"go-vllm-api/internal/proxy"
	"go-vllm-api/internal/repository"

	"go.uber.org/zap"
)

type Scheduler struct {
	logger              *zap.Logger
	gpuMonitor          *GPUMonitor
	sysCtl              *SystemController
	redis               *repository.RedisRepo
	cfg                 *config.AppConfig
	llamaCppMgr         *LlamaCppManager
	vllmManager         *VLLMManager
	proxy               *proxy.VLLMProxy
	runningModels       map[string]time.Time
	preloaded           map[string]bool
	modelLastUsed       map[string]time.Time
	modelSwitchTime     map[string]time.Time
	currentModel        string
	defaultModel        string
	mu                  sync.RWMutex
	rateLimiter         *RateLimiter
	switchingInProgress bool
	streamActive        map[string]int64
	zombieCheckerCancel context.CancelFunc
}

func NewScheduler(logger *zap.Logger, gpuMonitor *GPUMonitor, sysCtl *SystemController, redis *repository.RedisRepo, cfg *config.AppConfig, llamaCppMgr *LlamaCppManager, vllmManager *VLLMManager, vllmProxy *proxy.VLLMProxy) *Scheduler {
	s := &Scheduler{
		logger:          logger,
		gpuMonitor:      gpuMonitor,
		sysCtl:          sysCtl,
		redis:           redis,
		cfg:             cfg,
		llamaCppMgr:     llamaCppMgr,
		vllmManager:     vllmManager,
		proxy:           vllmProxy,
		runningModels:   make(map[string]time.Time),
		preloaded:       make(map[string]bool),
		modelLastUsed:   make(map[string]time.Time),
		modelSwitchTime: make(map[string]time.Time),
		rateLimiter:     NewRateLimiter(redis, logger),
		streamActive:    make(map[string]int64),
	}
	s.initPreloaded()
	return s
}

func (s *Scheduler) GetRateLimiter() *RateLimiter {
	return s.rateLimiter
}

func (s *Scheduler) GetVLLMManager() *VLLMManager {
	return s.vllmManager
}

func (s *Scheduler) initPreloaded() {
	for name, mc := range s.cfg.Models {
		if mc.Preload {
			s.preloaded[name] = true
		}
	}
}

func (s *Scheduler) SetConfig(cfg *config.AppConfig) {
	s.mu.Lock()
	s.cfg = cfg
	s.preloaded = make(map[string]bool)
	for name, mc := range cfg.Models {
		if mc.Preload {
			s.preloaded[name] = true
		}
	}
	s.mu.Unlock()
}

func (s *Scheduler) GetAvailableModels() []string {
	s.mu.RLock()
	defer s.mu.RUnlock()
	var models []string
	for name := range s.cfg.Models {
		models = append(models, name)
	}
	return models
}

func (s *Scheduler) findMatchingModelLocked(name string) string {
	if _, ok := s.cfg.Models[name]; ok {
		return name
	}
	lower := strings.ToLower(name)
	for cfgName := range s.cfg.Models {
		if strings.ToLower(cfgName) == lower {
			return cfgName
		}
	}
	for cfgName := range s.cfg.Models {
		cfgLower := strings.ToLower(cfgName)
		if strings.Contains(cfgLower, lower) || strings.Contains(lower, cfgLower) {
			return cfgName
		}
	}
	for cfgName := range s.cfg.Models {
		normInput := strings.ReplaceAll(strings.ToLower(name), "-", "")
		normCfg := strings.ReplaceAll(strings.ToLower(cfgName), "-", "")
		if strings.Contains(normInput, normCfg) || strings.Contains(normCfg, normInput) {
			return cfgName
		}
	}
	return ""
}

func (s *Scheduler) FindMatchingModel(name string) string {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.findMatchingModelLocked(name)
}

func (s *Scheduler) IsModelAvailable(name string) bool {
	return s.FindMatchingModel(name) != ""
}

func (s *Scheduler) GetModelConfig(name string) *config.ModelConfig {
	s.mu.RLock()
	defer s.mu.RUnlock()
	matched := s.findMatchingModelLocked(name)
	if matched == "" {
		return nil
	}
	mc := s.cfg.Models[matched]
	return &mc
}

func (s *Scheduler) GetModelPort(name string) int {
	mc := s.GetModelConfig(name)
	if mc != nil {
		return mc.Port
	}
	return 8000
}

func (s *Scheduler) GetModelService(name string) string {
	mc := s.GetModelConfig(name)
	if mc != nil {
		return mc.Service
	}
	return ""
}

func (s *Scheduler) GetModelPath(name string) string {
	mc := s.GetModelConfig(name)
	if mc != nil {
		return mc.ModelPath
	}
	return name
}

func (s *Scheduler) GetModelSupportsImages(name string) bool {
	mc := s.GetModelConfig(name)
	if mc != nil {
		return mc.SupportsImages
	}
	return false
}

func (s *Scheduler) GetModelSupportsToolCalling(name string) bool {
	mc := s.GetModelConfig(name)
	if mc != nil {
		return mc.SupportsToolCalling
	}
	return false
}

func (s *Scheduler) GetModelSupportsImageGeneration(name string) bool {
	mc := s.GetModelConfig(name)
	if mc != nil {
		return mc.SupportsImageGeneration
	}
	return false
}

func (s *Scheduler) GetModelBackendType(name string) string {
	mc := s.GetModelConfig(name)
	if mc != nil {
		if mc.Service == "llama_cpp" {
			return "llama_cpp"
		}
		return "vllm"
	}
	return ""
}

func (s *Scheduler) IsModelRunning(name string) bool {
	matched := s.FindMatchingModel(name)
	if matched == "" {
		return false
	}
	backendType := s.GetModelBackendType(matched)

	if backendType == "llama_cpp" {
		running := s.llamaCppMgr.IsServerRunning(matched)
		s.mu.Lock()
		if running {
			if _, ok := s.runningModels[matched]; !ok {
				s.runningModels[matched] = time.Now()
			}
		} else {
			delete(s.runningModels, matched)
		}
		s.mu.Unlock()
		return running
	}

	mc := s.GetModelConfig(matched)
	if mc == nil {
		return false
	}

	port := s.GetModelPort(matched)
	serviceRunning := mc.Service != "" && s.sysCtl.IsServiceRunning(mc.Service)
	portActive := port > 0 && s.sysCtl.GetProcessInfo(port)
	
	if !portActive && serviceRunning {
		s.logger.Debug("service running but port process not detected, allowing", 
			zap.String("model", matched), zap.String("service", mc.Service))
		portActive = true
	}
	
	if portActive || serviceRunning {
		currentModelPath := s.getCurrentVLLMModelPath()

		// 检查是否在切换窗口期内（2分钟）
		s.mu.RLock()
		switchTime, inGracePeriod := s.modelSwitchTime[matched]
		isRecentlySwitched := inGracePeriod && time.Since(switchTime) < 2*time.Minute
		_, inRunningModels := s.runningModels[matched]
		s.mu.RUnlock()

		// 如果在切换窗口期内且在运行模型列表中，先跳过路径检查
		if currentModelPath != "" && mc.ModelPath != "" && currentModelPath != mc.ModelPath {
			if !isRecentlySwitched || !inRunningModels {
				// Check if service itself is running even though paths differ (systemd override may handle this)
				if mc.Service != "" && s.sysCtl.IsServiceRunning(mc.Service) {
					s.logger.Info("vllm path mismatch but service is running, checking via API",
						zap.String("model", matched),
						zap.String("expected", mc.ModelPath),
						zap.String("actual", currentModelPath))
					actualModel := s.detectCurrentVLLMModel()
					if actualModel != "" && actualModel == matched {
						goto markRunning
					}
				}
				s.mu.Lock()
				delete(s.runningModels, matched)
				s.mu.Unlock()
				return false
			}
		}

		if mc.Service != "" && !s.sysCtl.IsServiceRunning(mc.Service) {
			s.mu.Lock()
			delete(s.runningModels, matched)
			s.mu.Unlock()
			return false
		}
	markRunning:
		s.mu.Lock()
		if _, ok := s.runningModels[matched]; !ok {
			s.runningModels[matched] = time.Now()
		}
		s.mu.Unlock()
		return true
	}
	s.mu.Lock()
	delete(s.runningModels, matched)
	s.mu.Unlock()
	return false
}

func (s *Scheduler) getCurrentVLLMModelPath() string {
	if s.cfg == nil || s.cfg.VLLM.StartScript == "" {
		return ""
	}

	stateFile := filepath.Join(filepath.Dir(s.cfg.VLLM.StartScript), ".vllm_model_path")
	data, err := os.ReadFile(stateFile)
	if err != nil {
		return ""
	}

	return strings.TrimSpace(string(data))
}

func (s *Scheduler) detectCurrentVLLMModel() string {
	var port int
	if s.vllmManager != nil {
		port = s.vllmManager.DiscoverVLLMPort()
	} else if s.cfg != nil && s.cfg.VLLM.DefaultPort > 0 {
		port = s.cfg.VLLM.DefaultPort
	} else {
		port = 8000
	}

	url := fmt.Sprintf("http://localhost:%d/v1/models", port)
	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Get(url)
	if err != nil {
		s.logger.Debug("failed to query vllm /v1/models", zap.Error(err))
		return ""
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return ""
	}

	var result struct {
		Data []struct {
			ID string `json:"id"`
		} `json:"data"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		s.logger.Debug("failed to decode vllm models response", zap.Error(err))
		return ""
	}

	if len(result.Data) == 0 {
		return ""
	}

	modelID := result.Data[0].ID
	for name, mc := range s.cfg.Models {
		if mc.ModelPath == modelID || name == modelID || strings.Contains(modelID, name) || strings.Contains(name, modelID) {
			return name
		}
	}
	return modelID
}

func (s *Scheduler) shouldSkipKeepAlivePreload(name string) bool {
	if s.GetModelBackendType(name) != "vllm" {
		return false
	}
	s.mu.RLock()
	currentModel := s.currentModel
	s.mu.RUnlock()
	if currentModel != "" && currentModel != name {
		return true
	}
	mc := s.GetModelConfig(name)
	if mc == nil {
		return false
	}
	currentModelPath := s.getCurrentVLLMModelPath()
	if currentModelPath == "" {
		s.mu.RLock()
		hasCurrent := s.currentModel != ""
		s.mu.RUnlock()
		return hasCurrent
	}
	return currentModelPath != mc.ModelPath
}

func (s *Scheduler) GetMinAvailableMemory() int64 {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return config.ParseMemorySize(s.cfg.Settings.MinAvailableMemory)
}

func (s *Scheduler) GetConcurrencyLimit() int {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.cfg.Settings.ConcurrencyLimit
}

func (s *Scheduler) GetStreamConcurrencyLimit() int {
	s.mu.RLock()
	defer s.mu.RUnlock()
	if s.cfg.Settings.StreamConcurrencyLimit > 0 {
		return s.cfg.Settings.StreamConcurrencyLimit
	}
	return s.cfg.Settings.ConcurrencyLimit
}

func (s *Scheduler) GetStreamMaxDuration() time.Duration {
	s.mu.RLock()
	defer s.mu.RUnlock()
	if s.cfg.Settings.StreamMaxDuration > 0 {
		return time.Duration(s.cfg.Settings.StreamMaxDuration) * time.Minute
	}
	return 30 * time.Minute
}

func (s *Scheduler) AcquireStreamSlot(model string) bool {
	limit := s.GetStreamConcurrencyLimit()
	s.mu.Lock()
	s.streamActive[model]++
	current := s.streamActive[model]
	s.mu.Unlock()
	if current > int64(limit) {
		s.mu.Lock()
		s.streamActive[model]--
		s.mu.Unlock()
		return false
	}
	return true
}

func (s *Scheduler) ReleaseStreamSlot(model string) {
	s.mu.Lock()
	if s.streamActive[model] > 0 {
		s.streamActive[model]--
	}
	s.mu.Unlock()
}

func (s *Scheduler) GetStreamActiveCount(model string) int {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return int(s.streamActive[model])
}

func (s *Scheduler) GetMaxQueueSize() int {
	s.mu.RLock()
	defer s.mu.RUnlock()
	if s.cfg.Settings.MaxQueueSize > 0 {
		return s.cfg.Settings.MaxQueueSize
	}
	return 100
}

func (s *Scheduler) StartZombieChecker(ctx context.Context) {
	interval := 5 * time.Minute
	idleTimeout := 5 * time.Minute
	s.mu.RLock()
	if s.cfg.Settings.ZombieCheckInterval > 0 {
		interval = time.Duration(s.cfg.Settings.ZombieCheckInterval) * time.Second
	}
	if s.cfg.Settings.ZombieIdleTimeout > 0 {
		idleTimeout = time.Duration(s.cfg.Settings.ZombieIdleTimeout) * time.Second
	}
	s.mu.RUnlock()

	zombieCtx, cancel := context.WithCancel(ctx)
	s.zombieCheckerCancel = cancel

	ticker := time.NewTicker(interval)
	defer ticker.Stop()
	for {
		select {
		case <-zombieCtx.Done():
			return
		case <-ticker.C:
			s.mu.Lock()
			now := time.Now()
			for model, lastUsed := range s.modelLastUsed {
				if now.Sub(lastUsed) > idleTimeout {
					active := s.rateLimiter.GetActiveRequests(model)
					streamActive := s.streamActive[model]
					if active == 0 && streamActive == 0 && s.IsModelRunning(model) && !s.preloaded[model] {
						s.logger.Info("zombie checker: idle model detected", zap.String("model", model), zap.Duration("idle", now.Sub(lastUsed)))
					}
				}
			}
			for model, count := range s.streamActive {
				if count > 0 {
					lastUsed, hasLast := s.modelLastUsed[model]
					if hasLast && now.Sub(lastUsed) > idleTimeout {
						s.logger.Warn("zombie checker: stale stream connection detected, releasing slots", zap.String("model", model), zap.Int64("stale_slots", count))
						s.streamActive[model] = 0
					}
				}
			}
			s.mu.Unlock()

			goroutineCount := runtime.NumGoroutine()
			if goroutineCount > 500 {
				s.logger.Warn("goroutine count exceeds threshold", zap.Int("count", goroutineCount), zap.Int("threshold", 500))
			}
		}
	}
}

func (s *Scheduler) AcquireRequest(model string) bool {
	limit := s.GetConcurrencyLimit()
	return s.rateLimiter.AcquireRequest(model, limit)
}

func (s *Scheduler) ReleaseRequest(model string) {
	s.rateLimiter.ReleaseRequest(model)
	matched := s.FindMatchingModel(model)
	if matched == "" {
		matched = model
	}
	s.mu.Lock()
	s.modelLastUsed[matched] = time.Now()
	s.mu.Unlock()
}

func (s *Scheduler) GetActiveRequests(model string) int {
	return s.rateLimiter.GetActiveRequests(model)
}

func (s *Scheduler) CanAcceptRequest(model string) bool {
	if !s.IsModelAvailable(model) {
		return false
	}
	mem := s.gpuMonitor.GetMemoryUsage()
	if mem == nil || mem.Available < s.GetMinAvailableMemory() {
		return false
	}
	return s.rateLimiter.CanAcceptRequest(model, s.GetConcurrencyLimit())
}

func (s *Scheduler) IsQueueAvailable(model string) bool {
	return s.rateLimiter.GetTotalQueueLength(model) < s.GetMaxQueueSize()
}

func (s *Scheduler) GetQueueLength(model string) int {
	return s.rateLimiter.GetTotalQueueLength(model)
}

func (s *Scheduler) WaitForSlot(ctx context.Context, model string, timeout time.Duration) bool {
	return s.rateLimiter.WaitForSlot(ctx, model, s.GetConcurrencyLimit(), timeout)
}

func (s *Scheduler) GetMaxModelLen(name string) int {
	mc := s.GetModelConfig(name)
	if mc != nil && mc.MaxModelLen > 0 {
		return mc.MaxModelLen
	}
	s.mu.RLock()
	defaultLen := s.cfg.VLLM.DefaultMaxModelLen
	s.mu.RUnlock()
	if defaultLen > 0 {
		return defaultLen
	}
	return 0
}

func (s *Scheduler) IsModelPreloaded(name string) bool {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.preloaded[name]
}

func (s *Scheduler) GetPreloadedModels() []string {
	s.mu.RLock()
	defer s.mu.RUnlock()
	var models []string
	for name := range s.preloaded {
		models = append(models, name)
	}
	return models
}

func (s *Scheduler) GetCurrentModelName() string {
	s.mu.RLock()
	defer s.mu.RUnlock()

	// 首先尝试通过 vllm API 动态检测
	if s.cfg != nil && s.cfg.VLLM.StartScript != "" {
		modelName := s.detectCurrentVLLMModel()
		if modelName != "" {
			return modelName
		}
	}

	// 回退到状态文件检测
	if s.cfg != nil && s.cfg.VLLM.StartScript != "" {
		stateFile := filepath.Join(filepath.Dir(s.cfg.VLLM.StartScript), ".vllm_model_path")
		data, err := os.ReadFile(stateFile)
		if err == nil {
			modelPath := strings.TrimSpace(string(data))
			for name, mc := range s.cfg.Models {
				if mc.ModelPath == modelPath {
					return name
				}
			}
			return modelPath
		}
	}
	return ""
}

func (s *Scheduler) GetDefaultModel() string {
	s.mu.RLock()
	defaultModel := s.defaultModel
	s.mu.RUnlock()
	if defaultModel != "" && s.IsModelAvailable(defaultModel) {
		return defaultModel
	}
	return ""
}

func (s *Scheduler) SetDefaultModel(name string) bool {
	if !s.IsModelAvailable(name) {
		return false
	}
	s.mu.Lock()
	s.defaultModel = name
	s.mu.Unlock()
	return true
}

func (s *Scheduler) ClearDefaultModel() {
	s.mu.Lock()
	s.defaultModel = ""
	s.mu.Unlock()
}

func (s *Scheduler) MarkModelSelected(name string) {
	matched := s.FindMatchingModel(name)
	if matched == "" {
		matched = name
	}
	s.mu.Lock()
	s.runningModels[matched] = time.Now()
	s.modelLastUsed[matched] = time.Now()
	s.modelSwitchTime[matched] = time.Now()
	s.mu.Unlock()

	if s.vllmManager != nil {
		s.vllmManager.RefreshVLLMPortCache()
	}
}

func (s *Scheduler) MarkModelRunning(name string) {
	matched := s.FindMatchingModel(name)
	if matched == "" {
		matched = name
	}
	s.mu.Lock()
	s.runningModels[matched] = time.Now()
	s.modelLastUsed[matched] = time.Now()
	s.modelSwitchTime[matched] = time.Now()
	s.mu.Unlock()
}

func (s *Scheduler) SchedulePreload(name string) bool {
	if !s.IsModelAvailable(name) {
		return false
	}
	s.mu.Lock()
	s.preloaded[name] = true
	if mc, ok := s.cfg.Models[name]; ok {
		mc.Preload = true
		s.cfg.Models[name] = mc
	}
	s.mu.Unlock()
	return true
}

func (s *Scheduler) CancelPreload(name string) bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	if !s.preloaded[name] {
		return false
	}
	delete(s.preloaded, name)
	if mc, ok := s.cfg.Models[name]; ok {
		mc.Preload = false
		s.cfg.Models[name] = mc
	}
	return true
}

func (s *Scheduler) StartModel(ctx context.Context, name string) (bool, error) {
	matched := s.FindMatchingModel(name)
	if matched == "" {
		return false, fmt.Errorf("model not found: %s", name)
	}
	mc := s.GetModelConfig(matched)
	if mc == nil {
		return false, fmt.Errorf("model config not found: %s", name)
	}

	backendType := s.GetModelBackendType(matched)

	if backendType == "llama_cpp" {
		return s.startLlamaCppModel(ctx, matched, mc)
	}

	return s.startVLLMModel(ctx, matched, mc)
}

func (s *Scheduler) startLlamaCppModel(ctx context.Context, matched string, mc *config.ModelConfig) (bool, error) {
	if s.llamaCppMgr.IsServerRunning(matched) {
		s.mu.Lock()
		s.runningModels[matched] = time.Now()
		s.mu.Unlock()
		s.logger.Info("llama_cpp model already running", zap.String("model", matched))
		return true, nil
	}

	if err := s.ensureMemoryAvailable(ctx, matched); err != nil {
		return false, fmt.Errorf("memory check failed: %w", err)
	}

	err := s.llamaCppMgr.StartServerByName(ctx, matched)
	if err != nil {
		s.logger.Error("failed to start llama_cpp model", zap.String("model", matched), zap.Error(err))
		return false, err
	}

	s.mu.Lock()
	s.runningModels[matched] = time.Now()
	s.modelLastUsed[matched] = time.Now()
	s.modelSwitchTime[matched] = time.Now()
	s.mu.Unlock()
	s.logger.Info("llama_cpp model started", zap.String("model", matched))
	return true, nil
}

func (s *Scheduler) startVLLMModel(ctx context.Context, matched string, mc *config.ModelConfig) (bool, error) {
	if s.sysCtl.IsServiceRunning(mc.Service) {
		currentModelPath := s.getCurrentVLLMModelPath()
		if currentModelPath == "" || currentModelPath == mc.ModelPath {
			s.mu.Lock()
			s.runningModels[matched] = time.Now()
			s.mu.Unlock()
			s.logger.Info("vllm service running with correct model", zap.String("model", matched))
			return true, nil
		}

		return s.switchVLLMModel(ctx, matched, mc)
	}

	if err := s.ensureMemoryAvailable(ctx, matched); err != nil {
		return false, fmt.Errorf("memory check failed: %w", err)
	}

	success := s.sysCtl.StartService(mc.Service)
	if success {
		s.mu.Lock()
		s.runningModels[matched] = time.Now()
		s.modelLastUsed[matched] = time.Now()
		s.modelSwitchTime[matched] = time.Now()
		s.mu.Unlock()
		s.logger.Info("vllm model started", zap.String("model", matched), zap.String("service", mc.Service))
		return true, nil
	}

	s.logger.Error("failed to start vllm service", zap.String("model", matched), zap.String("service", mc.Service))
	return false, fmt.Errorf("failed to start service %s for model %s", mc.Service, matched)
}

func (s *Scheduler) ensureMemoryAvailable(ctx context.Context, modelName string) error {
	mem := s.gpuMonitor.GetMemoryUsage()
	if mem == nil {
		s.logger.Warn("GPU memory info unavailable, skipping memory check", zap.String("model", modelName))
		return nil
	}

	mc := s.GetModelConfig(modelName)
	if mc == nil {
		return nil
	}

	requiredMem := config.ParseMemorySize(mc.RequiredMemory)
	if mem.Available >= requiredMem+s.GetMinAvailableMemory() {
		return nil
	}

	s.logger.Warn("insufficient memory for model", 
		zap.String("model", modelName),
		zap.Int64("available", mem.Available),
		zap.Int64("required", requiredMem))

	ok, err := s.freeUpMemory(ctx, modelName)
	if !ok {
		return fmt.Errorf("could not free enough memory: %w", err)
	}

	s.logger.Info("memory freed successfully", zap.String("model", modelName))
	return nil
}

func (s *Scheduler) switchVLLMModel(ctx context.Context, matched string, mc *config.ModelConfig) (bool, error) {
	if s.vllmManager == nil {
		return false, fmt.Errorf("vllm manager unavailable for model switch")
	}

	s.logger.Info("starting vllm model switch", zap.String("model", matched), zap.String("path", mc.ModelPath))

	if err := s.vllmManager.SwitchModel(ctx, mc.ModelPath); err != nil {
		s.logger.Error("failed to prepare model switch", zap.String("model", matched), zap.Error(err))
		return false, fmt.Errorf("prepare model switch: %w", err)
	}

	if err := s.waitForActiveRequestsToComplete(matched, 30); err != nil {
		s.logger.Warn("active requests did not complete in time", zap.String("model", matched), zap.Error(err))
	}

	if !s.sysCtl.RestartService(mc.Service) {
		s.logger.Error("failed to restart vllm service", zap.String("service", mc.Service))
		return false, fmt.Errorf("restart service %s failed", mc.Service)
	}

	s.mu.Lock()
	s.runningModels[matched] = time.Now()
	s.modelLastUsed[matched] = time.Now()
	s.modelSwitchTime[matched] = time.Now()
	s.currentModel = matched
	s.mu.Unlock()

	s.logger.Info("vllm model switched successfully", zap.String("model", matched), zap.String("path", mc.ModelPath))
	return true, nil
}

func (s *Scheduler) waitForActiveRequestsToComplete(modelName string, timeoutSeconds int) error {
	deadline := time.Now().Add(time.Duration(timeoutSeconds) * time.Second)
	
	for time.Now().Before(deadline) {
		if s.GetActiveRequests(modelName) == 0 {
			return nil
		}
		time.Sleep(500 * time.Millisecond)
	}
	
	return fmt.Errorf("timeout waiting for active requests to complete")
}

func (s *Scheduler) StopModel(ctx context.Context, name string) bool {
	matched := s.FindMatchingModel(name)
	if matched == "" {
		return false
	}
	mc := s.GetModelConfig(matched)
	if mc == nil {
		return false
	}

	backendType := s.GetModelBackendType(matched)

	if backendType == "llama_cpp" {
		err := s.llamaCppMgr.StopServer(matched)
		if err != nil {
			s.logger.Error("failed to stop llama_cpp model", zap.String("model", matched), zap.Error(err))
			return false
		}
		s.mu.Lock()
		delete(s.runningModels, matched)
		s.mu.Unlock()
		s.logger.Info("llama_cpp model stopped", zap.String("model", matched))
		return true
	}

	success := s.sysCtl.StopService(mc.Service)
	if success {
		s.mu.Lock()
		delete(s.runningModels, matched)
		s.mu.Unlock()
		s.logger.Info("model stopped", zap.String("model", matched))
	}
	return success
}

func (s *Scheduler) SwitchModel(ctx context.Context, name string) bool {
	matched := s.FindMatchingModel(name)
	if matched == "" {
		return false
	}
	mc := s.GetModelConfig(matched)
	if mc == nil {
		return false
	}
	mem := s.gpuMonitor.GetMemoryUsage()
	if mem != nil {
		requiredMem := config.ParseMemorySize(mc.RequiredMemory)
		if mem.Available < requiredMem+s.GetMinAvailableMemory() {
			ok, _ := s.freeUpMemory(ctx, matched)
			if !ok {
				return false
			}
		}
	}

	if s.vllmManager != nil {
		if err := s.vllmManager.SwitchModel(ctx, mc.ModelPath); err != nil {
			s.logger.Error("failed to switch vllm model state", zap.String("model", matched), zap.Error(err))
			return false
		}
	}

	success := s.sysCtl.RestartService(mc.Service)
	if success {
		s.mu.Lock()
		s.runningModels[matched] = time.Now()
		s.modelLastUsed[matched] = time.Now()
		s.mu.Unlock()
		s.logger.Info("model switched via restart", zap.String("model", matched))
	}
	return success
}

func (s *Scheduler) HotSwitchModel(ctx context.Context, name string) (bool, error) {
	matched := s.FindMatchingModel(name)
	if matched == "" {
		return false, fmt.Errorf("model not found: %s", name)
	}
	mc := s.GetModelConfig(matched)
	if mc == nil {
		return false, fmt.Errorf("model config not found: %s", matched)
	}

	mem := s.gpuMonitor.GetMemoryUsage()
	if mem != nil {
		requiredMem := config.ParseMemorySize(mc.RequiredMemory)
		if mem.Available < requiredMem+s.GetMinAvailableMemory() {
			ok, err := s.freeUpMemory(ctx, matched)
			if !ok {
				return false, fmt.Errorf("insufficient memory: %w", err)
			}
		}
	}

	if s.vllmManager == nil {
		return false, fmt.Errorf("vllm manager unavailable")
	}

	if err := s.vllmManager.SwitchModel(ctx, mc.ModelPath); err != nil {
		s.logger.Error("failed to switch vllm model state", zap.String("model", matched), zap.Error(err))
		return false, fmt.Errorf("switch vllm model state: %w", err)
	}

	success := s.sysCtl.RestartService(mc.Service)
	if !success {
		return false, fmt.Errorf("failed to restart service %s", mc.Service)
	}

	if err := s.waitForServiceReady(ctx, mc.Service, 120); err != nil {
		s.logger.Error("service failed to become ready after restart", zap.String("service", mc.Service), zap.Error(err))
		return false, fmt.Errorf("service %s failed to become ready: %w", mc.Service, err)
	}

	s.mu.Lock()
	s.runningModels[matched] = time.Now()
	s.modelLastUsed[matched] = time.Now()
	s.mu.Unlock()
	s.logger.Info("model hot switched", zap.String("model", matched))

	return true, nil
}

func (s *Scheduler) WarmSwitchModel(ctx context.Context, name string) (bool, error) {
	matched := s.FindMatchingModel(name)
	if matched == "" {
		return false, fmt.Errorf("model not found: %s", name)
	}
	mc := s.GetModelConfig(matched)
	if mc == nil {
		return false, fmt.Errorf("model config not found: %s", matched)
	}

	mem := s.gpuMonitor.GetMemoryUsage()
	if mem != nil {
		requiredMem := config.ParseMemorySize(mc.RequiredMemory)
		if mem.Available < requiredMem+s.GetMinAvailableMemory() {
			ok, err := s.freeUpMemory(ctx, matched)
			if !ok {
				return false, fmt.Errorf("insufficient memory: %w", err)
			}
		}
	}

	if s.vllmManager == nil {
		return false, fmt.Errorf("vllm manager unavailable")
	}

	if err := s.vllmManager.SwitchModel(ctx, mc.ModelPath); err != nil {
		s.logger.Error("failed to switch vllm model state", zap.String("model", matched), zap.Error(err))
		return false, fmt.Errorf("switch vllm model state: %w", err)
	}

	success := s.sysCtl.RestartService(mc.Service)
	if !success {
		return false, fmt.Errorf("failed to restart service %s", mc.Service)
	}

	if err := s.waitForServiceReady(ctx, mc.Service, 120); err != nil {
		s.logger.Error("service failed to become ready after restart", zap.String("service", mc.Service), zap.Error(err))
		return false, fmt.Errorf("service %s failed to become ready: %w", mc.Service, err)
	}

	if err := s.vllmManager.SwitchModel(ctx, mc.ModelPath); err != nil {
		s.logger.Warn("failed to re-update vllm model state after restart", zap.String("model", matched), zap.Error(err))
	}

	port := s.vllmManager.GetCurrentPort()
	if port == 0 {
		port = 8000
	}

	if s.proxy != nil {
		vllmModelName := mc.ModelPath
		if vllmModelName == "" {
			vllmModelName = matched
		}

		payload := map[string]interface{}{
			"model": vllmModelName,
			"messages": []map[string]interface{}{
				{"role": "user", "content": "Hello"},
			},
			"max_tokens": 1,
			"stream":     false,
		}

		for i := 0; i < 30; i++ {
			select {
			case <-ctx.Done():
				return false, ctx.Err()
			default:
			}

			_, err := s.proxy.ChatCompletion(ctx, port, payload)
			if err == nil {
				break
			}

			time.Sleep(2 * time.Second)
		}
	}

	s.mu.Lock()
	s.currentModel = matched
	s.runningModels[matched] = time.Now()
	s.modelLastUsed[matched] = time.Now()
	s.mu.Unlock()
	s.logger.Info("model warm switched", zap.String("model", matched))

	return true, nil
}

func (s *Scheduler) freeUpMemory(ctx context.Context, targetModel string) (bool, error) {
	s.mu.RLock()
	var toStop []string
	for name := range s.runningModels {
		if name == targetModel {
			continue
		}
		matched := s.findMatchingModelLocked(name)
		if matched == "" {
			matched = name
		}
		if mc, ok := s.cfg.Models[matched]; ok && mc.KeepAlive {
			continue
		}
		toStop = append(toStop, name)
	}
	s.mu.RUnlock()

	for _, name := range toStop {
		s.StopModel(ctx, name)
		mem := s.gpuMonitor.GetMemoryUsage()
		if mem != nil {
			mc := s.GetModelConfig(targetModel)
			if mc != nil {
				required := config.ParseMemorySize(mc.RequiredMemory)
				if mem.Available >= required+s.GetMinAvailableMemory() {
					return true, nil
				}
			}
		}
	}
	return false, fmt.Errorf("could not free enough memory")
}

func (s *Scheduler) PreloadModels(ctx context.Context) {
	s.mu.RLock()
	var preloadOrder []string
	var keepAlive []string
	var normal []string
	for name := range s.preloaded {
		matched := s.findMatchingModelLocked(name)
		if matched == "" {
			matched = name
		}
		if mc, ok := s.cfg.Models[matched]; ok && mc.KeepAlive {
			keepAlive = append(keepAlive, name)
		} else {
			normal = append(normal, name)
		}
	}
	preloadOrder = append(preloadOrder, keepAlive...)
	preloadOrder = append(preloadOrder, normal...)
	s.mu.RUnlock()

	for _, name := range preloadOrder {
		if s.shouldSkipKeepAlivePreload(name) {
			s.logger.Info("skip preload for different active vllm target", zap.String("model", name))
			continue
		}
		if !s.IsModelRunning(name) {
			s.logger.Info("preloading model", zap.String("model", name))
			ok, _ := s.StartModel(ctx, name)
			if ok {
				s.logger.Info("preloaded model", zap.String("model", name))
			} else {
				s.logger.Warn("failed to preload model", zap.String("model", name))
			}
			time.Sleep(2 * time.Second)
		}
	}
}

func (s *Scheduler) PreloadWatcherLoop(ctx context.Context) {
	for {
		select {
		case <-ctx.Done():
			return
		case <-time.After(30 * time.Second):
			for _, name := range s.GetPreloadedModels() {
				mc := s.GetModelConfig(name)
				if mc != nil && mc.KeepAlive && !s.IsModelRunning(name) {
					if s.shouldSkipKeepAlivePreload(name) {
						s.logger.Info("skip keep-alive restart for different active vllm target", zap.String("model", name))
						continue
					}
					s.logger.Warn("preloaded model not running, restarting", zap.String("model", name))
					s.StartModel(ctx, name)
				}
			}
		}
	}
}

type PreloadStatusDetail struct {
	Preloaded     bool `json:"preloaded"`
	Running       bool `json:"running"`
	PreloadConfig bool `json:"preload_config"`
	KeepAlive     bool `json:"keep_alive"`
}

type PreloadStatus struct {
	PreloadedModels []string                       `json:"preloaded_models"`
	AllModels       []string                       `json:"all_models"`
	Status          map[string]PreloadStatusDetail `json:"status"`
}

func (s *Scheduler) GetPreloadStatus() *PreloadStatus {
	allModels := s.GetAvailableModels()
	status := make(map[string]PreloadStatusDetail)
	for _, m := range allModels {
		mc := s.GetModelConfig(m)
		status[m] = PreloadStatusDetail{
			Preloaded: s.IsModelPreloaded(m),
			Running:   s.IsModelRunning(m),
			PreloadConfig: func() bool {
				if mc != nil {
					return mc.Preload
				}
				return false
			}(),
			KeepAlive: func() bool {
				if mc != nil {
					return mc.KeepAlive
				}
				return false
			}(),
		}
	}
	return &PreloadStatus{
		PreloadedModels: s.GetPreloadedModels(),
		AllModels:       allModels,
		Status:          status,
	}
}

func (s *Scheduler) SwitchModelWithFallback(ctx context.Context, target string, fallback string) bool {
	if s.SwitchModel(ctx, target) {
		return true
	}
	if fallback != "" && fallback != target {
		s.logger.Info("primary switch failed, trying fallback", zap.String("target", target), zap.String("fallback", fallback))
		return s.SwitchModel(ctx, fallback)
	}
	return false
}

func (s *Scheduler) waitForServiceReady(ctx context.Context, serviceName string, timeoutSeconds int) error {
	checkInterval := 2 * time.Second
	maxWait := time.Duration(timeoutSeconds) * time.Second
	startTime := time.Now()

	for time.Since(startTime) < maxWait {
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
		}

		status := s.sysCtl.GetServiceStatus(serviceName)
		if status == "active" {
			s.logger.Info("service is active, verifying readiness", zap.String("service", serviceName))
			
			if s.isVLLMServiceReady() {
				return nil
			}
			s.logger.Info("service active but vLLM not ready yet", zap.String("service", serviceName))
		}

		elapsed := int(time.Since(startTime).Seconds())
		if elapsed%10 == 0 {
			s.logger.Info("waiting for service to become ready", zap.String("service", serviceName), zap.Int("elapsed_seconds", elapsed))
		}

		time.Sleep(checkInterval)
	}
	return fmt.Errorf("service %s did not become ready within %d seconds", serviceName, timeoutSeconds)
}

func (s *Scheduler) isVLLMServiceReady() bool {
	if s.vllmManager == nil {
		return true
	}
	
	port := s.vllmManager.GetCurrentPort()
	if port == 0 {
		port = 8000
	}
	
	url := fmt.Sprintf("http://localhost:%d/v1/models", port)
	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Get(url)
	if err != nil {
		return false
	}
	defer resp.Body.Close()
	
	return resp.StatusCode == http.StatusOK
}

func (s *Scheduler) FlushCache() {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.rateLimiter.Flush()
	s.logger.Info("scheduler cache flushed")
}

func (s *Scheduler) SetSwitchingInProgress(val bool) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.switchingInProgress = val
}

func (s *Scheduler) IsSwitchingInProgress() bool {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.switchingInProgress
}
