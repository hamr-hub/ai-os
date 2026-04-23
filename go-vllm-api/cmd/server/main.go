package main

import (
	"context"
	"flag"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"go-vllm-api/internal/config"
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

	"github.com/gin-gonic/gin"
	"go.uber.org/zap"
)

func main() {
	port := flag.Int("port", 35000, "Server port")
	configPath := flag.String("config", "configs/config.yaml", "Config file path")
	logDir := flag.String("log-dir", "", "Custom log directory")
	flag.Parse()

	zapLogger := logger.NewLogger(*logDir)
	defer zapLogger.Sync()

	cfg, err := config.Load(*configPath)
	if err != nil {
		zapLogger.Fatal("load config", zap.Error(err))
	}
	zapLogger.Info("config loaded", zap.String("path", *configPath))

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
	scheduler := service.NewScheduler(zapLogger, gpuMonitor, sysCtl, redisRepo, cfg)
	metricsCollector := service.NewMetricsCollector(redisRepo, zapLogger)
	promExporter := prometheus.NewPrometheusExporter()
	vllmProxy := proxy.NewVLLMProxy(zapLogger)
	wsManager := service.NewWSManager(zapLogger)
	cacheUpdater := service.NewCacheUpdater(gpuMonitor, scheduler, cacheService, zapLogger)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	gpuMonitor.Start(ctx)

	if redisRepo.IsConnected() {
		cacheUpdater.Start(ctx, metricsCollector)
		zapLogger.Info("cache updater started")
	}

	configWatcher := config.NewConfigWatcher(*configPath, zapLogger)
	configWatcher.RegisterCallback(func(newCfg *config.AppConfig) {
		scheduler.SetConfig(newCfg)
		zapLogger.Info("config reloaded via watcher")
	})
	if err := configWatcher.Start(); err != nil {
		zapLogger.Warn("config watcher start failed", zap.Error(err))
	}

	scheduler.PreloadModels(ctx)
	go scheduler.PreloadWatcherLoop(ctx)

	go broadcastStatusLoop(ctx, gpuMonitor, scheduler, wsManager, zapLogger)

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
	manageHandler := manage.NewManageHandler(scheduler, gpuMonitor, sysCtl, metricsCollector, cacheService, cacheUpdater, wsManager)
	healthHandler := health.NewHealthHandler(gpuMonitor, scheduler, metricsCollector, cacheService, promExporter)
	wsHandler := ws.NewWSHandler(wsManager, zapLogger)

	v1Handler.RegisterRoutes(r.Group(""))
	manageHandler.RegisterRoutes(r.Group(""))
	healthHandler.RegisterRoutes(r.Group(""))
	wsHandler.RegisterRoutes(r.Group(""))

	srv := &http.Server{
		Addr:    fmt.Sprintf(":%d", *port),
		Handler: r,
	}

	go func() {
		zapLogger.Info("server starting", zap.Int("port", *port))
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			zapLogger.Fatal("listen", zap.Error(err))
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	zapLogger.Info("shutting down server...")
	configWatcher.Stop()
	cacheUpdater.Stop()
	gpuMonitor.Stop()

	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer shutdownCancel()
	if err := srv.Shutdown(shutdownCtx); err != nil {
		zapLogger.Error("server forced shutdown", zap.Error(err))
	}
	zapLogger.Info("server exited")
}

func broadcastStatusLoop(ctx context.Context, gm *service.GPUMonitor, s *service.Scheduler, ws *service.WSManager, l *zap.Logger) {
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
		}
	}
}
