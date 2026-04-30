package service

import (
	"testing"

	"go-vllm-api/internal/config"

	"go.uber.org/zap"
)

func TestGetMaxModelLen_ModelSpecific(t *testing.T) {
	cfg := &config.AppConfig{
		Models: map[string]config.ModelConfig{
			"test-model": {
				MaxModelLen: 8192,
			},
		},
		VLLM: config.VLLMConfig{
			DefaultMaxModelLen: 32768,
		},
	}
	s := NewScheduler(zap.NewNop(), nil, nil, nil, cfg, nil, nil, nil)

	got := s.GetMaxModelLen("test-model")
	if got != 8192 {
		t.Errorf("GetMaxModelLen with model-specific value: got %d, want 8192", got)
	}
}

func TestGetMaxModelLen_FallbackToDefault(t *testing.T) {
	cfg := &config.AppConfig{
		Models: map[string]config.ModelConfig{
			"test-model": {
				MaxModelLen: 0,
			},
		},
		VLLM: config.VLLMConfig{
			DefaultMaxModelLen: 32768,
		},
	}
	s := NewScheduler(zap.NewNop(), nil, nil, nil, cfg, nil, nil, nil)

	got := s.GetMaxModelLen("test-model")
	if got != 32768 {
		t.Errorf("GetMaxModelLen fallback to default: got %d, want 32768", got)
	}
}

func TestGetMaxModelLen_UnknownModel(t *testing.T) {
	cfg := &config.AppConfig{
		Models: map[string]config.ModelConfig{},
		VLLM: config.VLLMConfig{
			DefaultMaxModelLen: 16384,
		},
	}
	s := NewScheduler(zap.NewNop(), nil, nil, nil, cfg, nil, nil, nil)

	got := s.GetMaxModelLen("unknown")
	if got != 16384 {
		t.Errorf("GetMaxModelLen for unknown model: got %d, want 16384", got)
	}
}

func TestGetMaxModelLen_NoDefault(t *testing.T) {
	cfg := &config.AppConfig{
		Models: map[string]config.ModelConfig{
			"test-model": {},
		},
		VLLM: config.VLLMConfig{},
	}
	s := NewScheduler(zap.NewNop(), nil, nil, nil, cfg, nil, nil, nil)

	got := s.GetMaxModelLen("test-model")
	if got != 0 {
		t.Errorf("GetMaxModelLen with no default: got %d, want 0", got)
	}
}
