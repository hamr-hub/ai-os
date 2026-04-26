package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"net"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"go-vllm-api/internal/config"
	"go-vllm-api/internal/handler/agent"
	"go-vllm-api/internal/handler/health"
	"go-vllm-api/internal/handler/manage"
	v1handler "go-vllm-api/internal/handler/v1"
	"go-vllm-api/internal/handler/ws"
	"go-vllm-api/internal/middleware"
	"go-vllm-api/internal/pkg/logger"
	"go-vllm-api/internal/pkg/prometheus"
	"go-vllm-api/internal/proxy"
	"go-vllm-api/internal/repository"
	"go-vllm-api/internal/service"
	"go-vllm-api/internal/tools"

	"github.com/gin-gonic/gin"
	"go.uber.org/zap"
)

type schedulerConfigApplier interface {
	SetConfig(*config.AppConfig)
}

type vllmConfigApplier interface {
	SetConfig(*config.VLLMConfig)
}

type llamaConfigApplier interface {
	RegisterModelsFromConfig(*config.AppConfig)
}

func applyRuntimeConfig(cfg *config.AppConfig, scheduler schedulerConfigApplier, vllmManager vllmConfigApplier, llamaCppMgr llamaConfigApplier, zapLogger *zap.Logger, source string) error {
	if cfg == nil {
		return errors.New("config is nil")
	}

	scheduler.SetConfig(cfg)
	vllmManager.SetConfig(&cfg.VLLM)
	llamaCppMgr.RegisterModelsFromConfig(cfg)
	zapLogger.Info("runtime config applied", zap.String("source", source), zap.Int("models", len(cfg.Models)))
	return nil
}

func reloadRuntimeConfig(configPath string, scheduler schedulerConfigApplier, vllmManager vllmConfigApplier, llamaCppMgr llamaConfigApplier, zapLogger *zap.Logger, source string) error {
	cfg, err := config.Load(configPath)
	if err != nil {
		return fmt.Errorf("reload config: %w", err)
	}

	return applyRuntimeConfig(cfg, scheduler, vllmManager, llamaCppMgr, zapLogger, source)
}

func exitCodeForListenError(err error) int {
	if errors.Is(err, syscall.EADDRINUSE) {
		return 98
	}
	return 1
}

func main() {
	port := flag.Int("port", 35001, "Server port")
	configPath := flag.String("config", "configs/config.yaml", "Config file path")
	logDir := flag.String("log-dir", "", "Custom log directory")
	flag.Parse()

	zapLogger := logger.NewLogger(*logDir)
	defer zapLogger.Sync()

	cfg, err := config.Load(*configPath)
	if err != nil {
		zapLogger.Fatal("load config", zap.Error(err))
	}
	zapLogger.Info("config loaded", zap.String("path", *configPath), zap.Int("models", len(cfg.Models)))

	redisRepo := repository.NewRedisRepo(
		cfg.Settings.Redis.Host,
		cfg.Settings.Redis.Port,
		cfg.Settings.Redis.DB,
		zapLogger,
	)
	if err := redisRepo.Connect(); err != nil {
		zapLogger.Warn("redis connect failed, running without cache", zap.Error(err))
	}
	defer redisRepo.Close()

	cacheService := service.NewCacheService(redisRepo)
	gpuMonitor := service.NewGPUMonitor(zapLogger)
	sysCtl := service.NewSystemController(zapLogger)
	vllmManager := service.NewVLLMManager(&cfg.VLLM, zapLogger)
	llamaCppMgr := service.NewLlamaCppManager(zapLogger, cfg)
	llamaCppMgr.RegisterModelsFromConfig(cfg)
	scheduler := service.NewScheduler(zapLogger, gpuMonitor, sysCtl, redisRepo, cfg, llamaCppMgr, vllmManager)
	metricsCollector := service.NewMetricsCollector(redisRepo, zapLogger)
	promExporter := prometheus.NewPrometheusExporter()
	vllmProxy := proxy.NewVLLMProxy(zapLogger)
	wsManager := service.NewWSManager(zapLogger)
	cacheUpdater := service.NewCacheUpdater(gpuMonitor, scheduler, cacheService, zapLogger)

	modelTesting := service.NewModelTestingFramework(zapLogger)

	toolRegistry := tools.GetRegistry()
	toolExecutor := tools.NewToolExecutor(toolRegistry, scheduler, gpuMonitor, vllmManager, sysCtl, llamaCppMgr, zapLogger)
	agentHandler := agent.NewAgentHandler(scheduler, gpuMonitor, toolExecutor, toolRegistry, zapLogger)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	gpuMonitor.Start(ctx)

	if redisRepo.IsConnected() {
		go cacheUpdater.Start(ctx, metricsCollector)
		zapLogger.Info("cache updater starting")
	}

	configWatcher := config.NewConfigWatcher(*configPath, zapLogger)
	configWatcher.RegisterCallback(func(newCfg *config.AppConfig) {
		if err := applyRuntimeConfig(newCfg, scheduler, vllmManager, llamaCppMgr, zapLogger, "watcher"); err != nil {
			zapLogger.Error("config reload via watcher failed", zap.Error(err))
		}
	})
	if err := configWatcher.Start(); err != nil {
		zapLogger.Warn("config watcher start failed", zap.Error(err))
	}

	go scheduler.PreloadModels(ctx)
	go scheduler.PreloadWatcherLoop(ctx)

	sysCollector := service.NewSystemStatusCollector(zapLogger, redisRepo)
	go broadcastStatusLoop(ctx, gpuMonitor, scheduler, wsManager, metricsCollector, sysCollector, zapLogger)

	gin.SetMode(gin.ReleaseMode)
	r := gin.New()
	r.Use(gin.Recovery())
	r.Use(middleware.CORS())
	r.Use(middleware.RequestID())
	r.Use(middleware.RequestTracking(zapLogger))
	r.Use(middleware.ErrorHandler())

	rateLimiter := middleware.NewRateLimitMiddlewareWithLimiter(100, 60, scheduler.GetRateLimiter())
	r.Use(rateLimiter.Handler())

	v1Handler := v1handler.NewV1Handler(scheduler, gpuMonitor, vllmProxy, metricsCollector, cacheService)
	manageHandler := manage.NewManageHandler(
		scheduler, gpuMonitor, sysCtl, sysCollector,
		metricsCollector, cacheService, cacheUpdater, wsManager,
		vllmManager, llamaCppMgr, modelTesting,
		redisRepo, *configPath,
	)
	healthHandler := health.NewHealthHandler(gpuMonitor, scheduler, metricsCollector, cacheService, promExporter)
	wsHandler := ws.NewWSHandler(wsManager, zapLogger)

	v1Handler.RegisterRoutes(r.Group(""))
	manageHandler.RegisterRoutes(r.Group(""))
	healthHandler.RegisterRoutes(r.Group(""))
	wsHandler.RegisterRoutes(r.Group(""))
	agentHandler.RegisterRoutes(r.Group(""))

	srv := &http.Server{
		Addr:              fmt.Sprintf(":%d", *port),
		Handler:           r,
		ReadHeaderTimeout: 10 * time.Second,
		ReadTimeout:       30 * time.Second,
		WriteTimeout:      0,
		IdleTimeout:       120 * time.Second,
	}

	listener, err := net.Listen("tcp", srv.Addr)
	if err != nil {
		exitCode := exitCodeForListenError(err)
		if exitCode == 98 {
			zapLogger.Error("listen address already in use", zap.Error(err), zap.String("addr", srv.Addr))
			os.Exit(exitCode)
		}
		zapLogger.Fatal("listen", zap.Error(err))
	}

	go func() {
		zapLogger.Info("server starting", zap.Int("port", *port))
		if err := srv.Serve(listener); err != nil && err != http.ErrServerClosed {
			zapLogger.Fatal("serve", zap.Error(err))
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM, syscall.SIGHUP)
	for {
		sig := <-quit
		if sig == syscall.SIGHUP {
			if err := reloadRuntimeConfig(*configPath, scheduler, vllmManager, llamaCppMgr, zapLogger, "signal"); err != nil {
				zapLogger.Error("runtime config reload failed", zap.Error(err))
			}
			continue
		}

		zapLogger.Info("shutting down server...", zap.String("signal", sig.String()))
		break
	}

	configWatcher.Stop()
	cacheUpdater.Stop()
	gpuMonitor.Stop()
	llamaCppMgr.CleanupAll()

	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer shutdownCancel()
	if err := srv.Shutdown(shutdownCtx); err != nil {
		zapLogger.Error("server forced shutdown", zap.Error(err))
	}
	zapLogger.Info("server exited")
}

func broadcastStatusLoop(ctx context.Context, gm *service.GPUMonitor, s *service.Scheduler, ws *service.WSManager, mc *service.MetricsCollector, sc *service.SystemStatusCollector, l *zap.Logger) {
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			gpuSummary := gm.GetStatus()
			models := s.GetAvailableModels()
			modelStatus := make(map[string]interface{})
			for _, m := range models {
				modelStatus[m] = map[string]interface{}{
					"running":         s.IsModelRunning(m),
					"port":            s.GetModelPort(m),
					"service":         s.GetModelService(m),
					"active_requests": s.GetActiveRequests(m),
					"preloaded":       s.IsModelPreloaded(m),
				}
			}
			ws.BroadcastStatus(gpuSummary, modelStatus)
			mc.SaveGPUHistory(gpuSummary)
			sc.SaveSystemHistory()
		}
	}
}
