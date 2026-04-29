package service

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
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
	if port > 0 && s.sysCtl.GetProcessInfo(port) {
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
				// 不在窗口期，执行正常的路径检查逻辑
				s.mu.Lock()
				delete(s.runningModels, matched)
				s.mu.Unlock()
				return false
			}
			// 在窗口期内，继续检查其他条件
		}
		
		if mc.Service != "" && !s.sysCtl.IsServiceRunning(mc.Service) {
			s.mu.Lock()
			delete(s.runningModels, matched)
			s.mu.Unlock()
			return false
		}
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
	currentModelPath := s.getCurrentVLLMModelPath()
	mc := s.GetModelConfig(name)
	if mc == nil || currentModelPath == "" {
		return false
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
	return s.rateLimiter.GetTotalQueueLength(model) < 100
}

func (s *Scheduler) GetQueueLength(model string) int {
	return s.rateLimiter.GetTotalQueueLength(model)
}

func (s *Scheduler) WaitForSlot(ctx context.Context, model string, timeout time.Duration) bool {
	return s.rateLimiter.WaitForSlot(ctx, model, s.GetConcurrencyLimit(), timeout)
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
		if s.llamaCppMgr.IsServerRunning(matched) {
			s.mu.Lock()
			s.runningModels[matched] = time.Now()
			s.mu.Unlock()
			return true, nil
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

		err := s.llamaCppMgr.StartServerByName(ctx, matched)
		if err != nil {
			s.logger.Error("failed to start llama_cpp model", zap.String("model", matched), zap.Error(err))
			return false, err
		}
		s.mu.Lock()
		s.runningModels[matched] = time.Now()
		s.mu.Unlock()
		s.logger.Info("llama_cpp model started", zap.String("model", matched))
		return true, nil
	}

	if s.sysCtl.IsServiceRunning(mc.Service) {
		currentModelPath := s.getCurrentVLLMModelPath()
		if currentModelPath == "" || currentModelPath == mc.ModelPath {
			s.mu.Lock()
			s.runningModels[matched] = time.Now()
			s.mu.Unlock()
			return true, nil
		}

		if s.vllmManager == nil {
			return false, fmt.Errorf("vllm manager unavailable for model switch")
		}
		if err := s.vllmManager.SwitchModel(ctx, mc.ModelPath); err != nil {
			return false, fmt.Errorf("switch vllm model state: %w", err)
		}
		if !s.sysCtl.RestartService(mc.Service) {
			return false, fmt.Errorf("restart service %s after switching model", mc.Service)
		}
		s.mu.Lock()
		s.runningModels[matched] = time.Now()
		s.modelLastUsed[matched] = time.Now()
		s.mu.Unlock()
		s.logger.Info("vllm model switched via restart", zap.String("model", matched), zap.String("path", mc.ModelPath))
		return true, nil
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
	success := s.sysCtl.StartService(mc.Service)
	if success {
		s.mu.Lock()
		s.runningModels[matched] = time.Now()
		s.mu.Unlock()
		s.logger.Info("model started", zap.String("model", matched))
		return true, nil
	}
	s.logger.Error("failed to start model", zap.String("model", matched))
	return false, fmt.Errorf("failed to start service %s for model %s", mc.Service, matched)
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

	if s.proxy == nil {
		return false, fmt.Errorf("vllm proxy unavailable")
	}

	port := s.vllmManager.GetCurrentPort()
	if port == 0 {
		port = 8000
	}

	vllmModelName := mc.ModelPath
	if vllmModelName == "" {
		vllmModelName = matched
	}

	payload := map[string]interface{}{
		"model":      vllmModelName,
		"messages": []map[string]interface{}{
			{"role": "user", "content": "Hello"},
		},
		"max_tokens": 1,
		"stream":     false,
	}

	_, err := s.proxy.ChatCompletion(ctx, port, payload)
	if err != nil {
		s.logger.Warn("warm switch probe request", zap.String("model", matched), zap.Error(err))
	}

	s.mu.Lock()
	s.currentModel = matched
	s.runningModels[matched] = time.Now()
	s.modelLastUsed[matched] = time.Now()
	s.mu.Unlock()
	s.logger.Info("model warm switched via chat probe", zap.String("model", matched), zap.Int("port", port))

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
