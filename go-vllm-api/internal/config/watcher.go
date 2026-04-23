package config

import (
	"fmt"
	"sync"
	"time"

	"github.com/fsnotify/fsnotify"
	"go.uber.org/zap"
)

type ConfigWatcher struct {
	path     string
	watcher  *fsnotify.Watcher
	callbacks []func(*AppConfig)
	stopCh   chan struct{}
	logger   *zap.Logger
	mu       sync.Mutex
}

func NewConfigWatcher(path string, logger *zap.Logger) *ConfigWatcher {
	return &ConfigWatcher{
		path:     path,
		stopCh:   make(chan struct{}),
		logger:   logger,
	}
}

func (cw *ConfigWatcher) RegisterCallback(cb func(*AppConfig)) {
	cw.mu.Lock()
	cw.callbacks = append(cw.callbacks, cb)
	cw.mu.Unlock()
}

func (cw *ConfigWatcher) Start() error {
	w, err := fsnotify.NewWatcher()
	if err != nil {
		return fmt.Errorf("create fsnotify watcher: %w", err)
	}
	cw.watcher = w
	if err := w.Add(cw.path); err != nil {
		return fmt.Errorf("watch config file: %w", err)
	}
	go cw.loop()
	cw.logger.Info("config watcher started", zap.String("path", cw.path))
	return nil
}

func (cw *ConfigWatcher) loop() {
	var lastReload time.Time
	for {
		select {
		case <-cw.stopCh:
			return
		case event, ok := <-cw.watcher.Events:
			if !ok {
				return
			}
			if event.Has(fsnotify.Write) || event.Has(fsnotify.Create) || event.Has(fsnotify.Rename) {
				if time.Since(lastReload) < 2*time.Second {
					continue
				}
				lastReload = time.Now()
				newCfg, err := Load(cw.path)
				if err != nil {
					cw.logger.Error("reload config failed", zap.Error(err))
					continue
				}
				Set(newCfg)
				cw.mu.Lock()
				cbs := cw.callbacks
				cw.mu.Unlock()
				for _, cb := range cbs {
					cb(newCfg)
				}
				cw.logger.Info("config reloaded")
			}
		case err, ok := <-cw.watcher.Errors:
			if !ok {
				return
			}
			cw.logger.Error("config watcher error", zap.Error(err))
		}
	}
}

func (cw *ConfigWatcher) Stop() {
	close(cw.stopCh)
	if cw.watcher != nil {
		cw.watcher.Close()
	}
	cw.logger.Info("config watcher stopped")
}
