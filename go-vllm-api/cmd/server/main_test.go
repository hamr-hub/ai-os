package main

import (
	"net"
	"os"
	"path/filepath"
	"testing"

	"go-vllm-api/internal/config"

	"go.uber.org/zap"
)

type stubScheduler struct {
	cfg *config.AppConfig
}

func (s *stubScheduler) SetConfig(cfg *config.AppConfig) {
	s.cfg = cfg
}

type stubVLLMManager struct {
	cfg *config.VLLMConfig
}

func (m *stubVLLMManager) SetConfig(cfg *config.VLLMConfig) {
	m.cfg = cfg
}

type stubLlamaManager struct {
	cfg *config.AppConfig
}

func (m *stubLlamaManager) RegisterModelsFromConfig(cfg *config.AppConfig) {
	m.cfg = cfg
}

func TestApplyRuntimeConfig(t *testing.T) {
	logger := zap.NewNop()
	scheduler := &stubScheduler{}
	vllmManager := &stubVLLMManager{}
	llamaManager := &stubLlamaManager{}
	cfg := &config.AppConfig{
		Models: map[string]config.ModelConfig{
			"demo": {Port: 8001},
		},
		VLLM: config.VLLMConfig{
			DefaultPort: 9000,
		},
	}

	if err := applyRuntimeConfig(cfg, scheduler, vllmManager, llamaManager, logger, "test"); err != nil {
		t.Fatalf("applyRuntimeConfig returned error: %v", err)
	}

	if scheduler.cfg != cfg {
		t.Fatalf("scheduler config not applied")
	}
	if vllmManager.cfg == nil || vllmManager.cfg.DefaultPort != 9000 {
		t.Fatalf("vllm config not applied")
	}
	if llamaManager.cfg != cfg {
		t.Fatalf("llama config not applied")
	}
}

func TestReloadRuntimeConfig(t *testing.T) {
	tempDir := t.TempDir()
	configPath := filepath.Join(tempDir, "config.yaml")
	configContent := []byte("models:\n  demo:\n    service: vllm\n    port: 8001\nvllm:\n  default_port: 9000\n")
	if err := os.WriteFile(configPath, configContent, 0644); err != nil {
		t.Fatalf("write temp config: %v", err)
	}

	logger := zap.NewNop()
	scheduler := &stubScheduler{}
	vllmManager := &stubVLLMManager{}
	llamaManager := &stubLlamaManager{}

	if err := reloadRuntimeConfig(configPath, scheduler, vllmManager, llamaManager, logger, "test"); err != nil {
		t.Fatalf("reloadRuntimeConfig returned error: %v", err)
	}

	if scheduler.cfg == nil || scheduler.cfg.Models["demo"].Port != 8001 {
		t.Fatalf("scheduler config was not reloaded")
	}
	if vllmManager.cfg == nil || vllmManager.cfg.DefaultPort != 9000 {
		t.Fatalf("vllm config was not reloaded")
	}
	if llamaManager.cfg == nil || llamaManager.cfg.Models["demo"].Port != 8001 {
		t.Fatalf("llama config was not reloaded")
	}
}

func TestExitCodeForListenError(t *testing.T) {
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	defer listener.Close()

	_, err = net.Listen("tcp", listener.Addr().String())
	if err == nil {
		t.Fatalf("expected address in use error")
	}

	if got := exitCodeForListenError(err); got != 98 {
		t.Fatalf("exitCodeForListenError() = %d, want 98", got)
	}
}
