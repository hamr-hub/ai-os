package config

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"

	"gopkg.in/yaml.v3"
)

type AppConfig struct {
	Models   map[string]ModelConfig `yaml:"models"`
	Settings SettingsConfig         `yaml:"settings"`
	VLLM     VLLMConfig             `yaml:"vllm"`
}

type ModelConfig struct {
	Service                string `yaml:"service"`
	Port                   int    `yaml:"port"`
	RequiredMemory         string `yaml:"required_memory"`
	Preload                bool   `yaml:"preload"`
	KeepAlive              bool   `yaml:"keep_alive"`
	ModelPath              string `yaml:"model_path"`
	SupportsImages         bool   `yaml:"supports_images"`
	SupportsToolCalling    bool   `yaml:"supports_tool_calling"`
	SupportsImageGeneration bool  `yaml:"supports_image_generation"`
	Description            string `yaml:"description"`
	ConcurrencyLimit       int    `yaml:"concurrency_limit"`
}

type SettingsConfig struct {
	ConcurrencyLimit    int            `yaml:"concurrency_limit"`
	MinAvailableMemory  string         `yaml:"min_available_memory"`
	RequestTimeout      int            `yaml:"request_timeout"`
	ModelStartTimeout   int            `yaml:"model_start_timeout"`
	PreloadTimeout      int            `yaml:"preload_timeout"`
	IdleTimeout         int            `yaml:"idle_timeout"`
	MemoryFlushInterval int            `yaml:"memory_flush_interval"`
	MemoryCleanupDelay  int            `yaml:"memory_cleanup_delay"`
	GPUMemoryUtilization float64       `yaml:"gpu_memory_utilization"`
	DefaultMemoryStrategy string       `yaml:"default_memory_strategy"`
	Redis               RedisConfig    `yaml:"redis"`
	Logging             LoggingConfig  `yaml:"logging"`
	Queue               QueueConfig    `yaml:"queue"`
	Priority            PriorityConfig `yaml:"priority"`
	Recovery            RecoveryConfig `yaml:"recovery"`
}

type RedisConfig struct {
	Host string `yaml:"host"`
	Port int    `yaml:"port"`
	DB   int    `yaml:"db"`
}

type LoggingConfig struct {
	LogDir string `yaml:"log_dir"`
}

type QueueConfig struct {
	MaxLength    int     `yaml:"max_length"`
	PollInterval float64 `yaml:"poll_interval"`
	WaitTimeout  int     `yaml:"wait_timeout"`
}

type PriorityConfig struct {
	Default string `yaml:"default"`
	Enabled bool   `yaml:"enabled"`
}

type RecoveryConfig struct {
	MaxRestartAttempts    int `yaml:"max_restart_attempts"`
	RestartCooldown       int `yaml:"restart_cooldown"`
	WatchdogCheckInterval int `yaml:"watchdog_check_interval"`
}

type VLLMConfig struct {
	ServiceName                string  `yaml:"service_name"`
	StartScript                string  `yaml:"start_script"`
	ModelBasePath              string  `yaml:"model_base_path"`
	DefaultPort                int     `yaml:"default_port"`
	DefaultGPUMemoryUtilization float64 `yaml:"default_gpu_memory_utilization"`
	DefaultMaxModelLen         int     `yaml:"default_max_model_len"`
}

func ParseMemorySize(sizeStr string) int64 {
	if sizeStr == "" {
		return 0
	}
	s := strings.TrimSpace(strings.ToUpper(sizeStr))
	multipliers := map[string]int64{
		"TB": 1 << 40,
		"GB": 1 << 30,
		"MB": 1 << 20,
		"KB": 1 << 10,
		"B":  1,
	}
	for suffix, mult := range multipliers {
		if strings.HasSuffix(s, suffix) {
			numStr := strings.TrimSpace(s[:len(s)-len(suffix)])
			if numStr == "" {
				return 0
			}
			num, err := strconv.ParseFloat(numStr, 64)
			if err != nil {
				return 0
			}
			return int64(num * float64(mult))
		}
	}
	num, err := strconv.ParseInt(s, 10, 64)
	if err != nil {
		return 0
	}
	return num
}

var (
	cfg     *AppConfig
	cfgOnce sync.Once
	cfgMu   sync.RWMutex
)

func Load(path string) (*AppConfig, error) {
	cfgMu.Lock()
	defer cfgMu.Unlock()

	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read config file: %w", err)
	}
	var c AppConfig
	if err := yaml.Unmarshal(data, &c); err != nil {
		return nil, fmt.Errorf("parse config yaml: %w", err)
	}
	cfg = &c
	return cfg, nil
}

func DefaultConfigPath() string {
	exe, err := os.Executable()
	if err != nil {
		return "configs/config.yaml"
	}
	return filepath.Join(filepath.Dir(exe), "configs", "config.yaml")
}

func Get() *AppConfig {
	cfgMu.RLock()
	defer cfgMu.RUnlock()
	return cfg
}

func Set(newCfg *AppConfig) {
	cfgMu.Lock()
	defer cfgMu.Unlock()
	cfg = newCfg
}
