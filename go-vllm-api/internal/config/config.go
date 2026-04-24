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
	LlamaCpp LlamaCppConfig         `yaml:"llama_cpp"`
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

	NGPULayers int      `yaml:"n_gpu_layers"`
	CtxSize    int      `yaml:"ctx_size"`
	NThreads   int      `yaml:"n_threads"`
	Host       string   `yaml:"host"`
	ExtraArgs  []string `yaml:"extra_args"`
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

type LlamaCppConfig struct {
	ServerModule     string `yaml:"server_module"`
	ModelsBasePath   string `yaml:"models_base_path"`
	DefaultNGPULayers int   `yaml:"default_n_gpu_layers"`
	DefaultCtxSize    int   `yaml:"default_ctx_size"`
	DefaultHost       string `yaml:"default_host"`
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

	// Environment variable overrides
	if redisURL := os.Getenv("REDIS_URL"); redisURL != "" {
		// Simple parsing for redis://host:port or redis://:password@host:port/db
		trimmed := strings.TrimPrefix(redisURL, "redis://")
		// Handle password/user if present
		if idx := strings.LastIndex(trimmed, "@"); idx != -1 {
			trimmed = trimmed[idx+1:]
		}
		// Handle DB if present
		if idx := strings.LastIndex(trimmed, "/"); idx != -1 {
			dbStr := trimmed[idx+1:]
			if db, err := strconv.Atoi(dbStr); err == nil {
				c.Settings.Redis.DB = db
			}
			trimmed = trimmed[:idx]
		}
		// Handle host:port
		parts := strings.Split(trimmed, ":")
		c.Settings.Redis.Host = parts[0]
		if len(parts) > 1 {
			if port, err := strconv.Atoi(parts[1]); err == nil {
				c.Settings.Redis.Port = port
			}
		}
	} else {
		if host := os.Getenv("REDIS_HOST"); host != "" {
			c.Settings.Redis.Host = host
		}
		if port := os.Getenv("REDIS_PORT"); port != "" {
			if p, err := strconv.Atoi(port); err == nil {
				c.Settings.Redis.Port = p
			}
		}
		if db := os.Getenv("REDIS_DB"); db != "" {
			if d, err := strconv.Atoi(db); err == nil {
				c.Settings.Redis.DB = d
			}
		}
	}

	if c.LlamaCpp.DefaultNGPULayers == 0 {
		c.LlamaCpp.DefaultNGPULayers = -1
	}
	if c.LlamaCpp.DefaultCtxSize == 0 {
		c.LlamaCpp.DefaultCtxSize = 4096
	}
	if c.LlamaCpp.DefaultHost == "" {
		c.LlamaCpp.DefaultHost = "0.0.0.0"
	}
	if c.LlamaCpp.ServerModule == "" {
		c.LlamaCpp.ServerModule = "llama_cpp.server"
	}
	if c.LlamaCpp.ModelsBasePath == "" {
		c.LlamaCpp.ModelsBasePath = c.VLLM.ModelBasePath
	}

	cfg = &c
	return cfg, nil
}

func Save(path string, c *AppConfig) error {
	data, err := yaml.Marshal(c)
	if err != nil {
		return fmt.Errorf("marshal config: %w", err)
	}
	if err := os.WriteFile(path, data, 0644); err != nil {
		return fmt.Errorf("write config file: %w", err)
	}
	return nil
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
