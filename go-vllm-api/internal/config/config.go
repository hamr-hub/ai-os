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
	Models      map[string]ModelConfig `yaml:"models"`
	Settings    SettingsConfig         `yaml:"settings"`
	VLLM        VLLMConfig             `yaml:"vllm"`
	LlamaCpp    LlamaCppConfig         `yaml:"llama_cpp"`
	Discovery   DiscoveryConfig        `yaml:"discovery"`
	GoApi       GoApiConfig            `yaml:"go_api"`
	AppController AppControllerConfig  `yaml:"app_controller"`
}

type GoApiConfig struct {
	Host              string           `yaml:"host"`
	Port              int              `yaml:"port"`
	ManageBackendURL  string           `yaml:"manage_backend_url"`
	AdminWhitelist    AdminWhitelistConfig `yaml:"admin_whitelist"`
	Auth              AuthConfig       `yaml:"auth"`
}

type AppControllerConfig struct {
	Host           string               `yaml:"host"`
	Port           int                  `yaml:"port"`
	AdminWhitelist AdminWhitelistConfig `yaml:"admin_whitelist"`
	WebSocket      WebSocketConfig      `yaml:"websocket"`
	CorsOrigins    []string             `yaml:"cors_origins"`
	TrustedProxies []string             `yaml:"trusted_proxies"`
	Auth           AuthConfig           `yaml:"auth"`
}

type AdminWhitelistConfig struct {
	Enabled              bool     `yaml:"enabled"`
	AllowedIPs           []string `yaml:"allowed_ips"`
	BlockWriteNonWhitelist bool   `yaml:"block_write_non_whitelist"`
}

type AuthConfig struct {
	Enabled bool     `yaml:"enabled"`
	APIKey  string   `yaml:"api_key"`
	APIKeys []string `yaml:"api_keys"`
}

type WebSocketConfig struct {
	Enabled      bool   `yaml:"enabled"`
	Path         string `yaml:"path"`
	PingInterval int    `yaml:"ping_interval"`
	PingTimeout  int    `yaml:"ping_timeout"`
}

type DiscoveryConfig struct {
	AutoDiscover   bool     `yaml:"auto_discover"`
	ScanPaths      []string `yaml:"scan_paths"`
	IgnorePatterns []string `yaml:"ignore_patterns"`
	Priority       string   `yaml:"priority"` // "scan_first" or "config_first"
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
	MaxModelLen            int    `yaml:"max_model_len"`

	NGPULayers int      `yaml:"n_gpu_layers"`
	CtxSize    int      `yaml:"ctx_size"`
	NThreads   int      `yaml:"n_threads"`
	Host       string   `yaml:"host"`
	ExtraArgs  []string `yaml:"extra_args"`
}

type SettingsConfig struct {
	ConcurrencyLimit    int            `yaml:"concurrency_limit"`
	StreamConcurrencyLimit int         `yaml:"stream_concurrency_limit"`
	StreamMaxDuration   int            `yaml:"stream_max_duration"`
	ZombieCheckInterval int            `yaml:"zombie_check_interval"`
	ZombieIdleTimeout   int            `yaml:"zombie_idle_timeout"`
	MaxQueueSize        int            `yaml:"max_queue_size"`
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
	TrustedProxies      []string       `yaml:"trusted_proxies"`
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
	VLLMHost                   string  `yaml:"vllm_host"`
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
	if c.VLLM.VLLMHost == "" {
		c.VLLM.VLLMHost = "localhost"
	}

	// Discovery defaults
	if c.Discovery.Priority == "" {
		c.Discovery.Priority = "scan_first"
	}
	if len(c.Discovery.ScanPaths) == 0 && c.VLLM.ModelBasePath != "" {
		c.Discovery.ScanPaths = []string{c.VLLM.ModelBasePath}
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
	envPath := os.Getenv("CONFIG_PATH")
	if envPath != "" {
		return envPath
	}
	exe, err := os.Executable()
	if err != nil {
		return "../config.yaml"
	}
	parentDir := filepath.Dir(filepath.Dir(exe))
	rootConfig := filepath.Join(parentDir, "config.yaml")
	if _, statErr := os.Stat(rootConfig); statErr == nil {
		return rootConfig
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

// DiscoveredModel represents a model discovered from directory scanning
type DiscoveredModel struct {
	Name          string
	Path          string
	EstimatedSize int64
	Service       string // "vllm" or "llama_cpp"
}

// MergeDiscoveredModels merges discovered models with existing config.
// If priority is "scan_first", discovered models take precedence.
// If priority is "config_first", existing config takes precedence.
func (c *AppConfig) MergeDiscoveredModels(discovered []DiscoveredModel) {
	if c.Models == nil {
		c.Models = make(map[string]ModelConfig)
	}

	scanFirst := c.Discovery.Priority == "scan_first"

	for _, dm := range discovered {
		existing, hasConfig := c.Models[dm.Name]

		if scanFirst {
			// Scan priority: use discovered model, apply config as extension
			mc := ModelConfig{
				Service:   dm.Service,
				ModelPath: dm.Path,
				Port:      c.VLLM.DefaultPort,
			}
			if dm.Service == "llama_cpp" {
				mc.Port = 8001 // Default llama.cpp port
			}

			// Apply config extensions if exists
			if hasConfig {
				if existing.Service != "" {
					mc.Service = existing.Service
				}
				if existing.Port != 0 {
					mc.Port = existing.Port
				}
				if existing.RequiredMemory != "" {
					mc.RequiredMemory = existing.RequiredMemory
				}
				if existing.Description != "" {
					mc.Description = existing.Description
				}
				mc.SupportsImages = existing.SupportsImages
				mc.SupportsToolCalling = existing.SupportsToolCalling
				mc.SupportsImageGeneration = existing.SupportsImageGeneration
				mc.Preload = existing.Preload
				mc.KeepAlive = existing.KeepAlive
				mc.ConcurrencyLimit = existing.ConcurrencyLimit
				mc.NGPULayers = existing.NGPULayers
				mc.CtxSize = existing.CtxSize
				mc.NThreads = existing.NThreads
				mc.Host = existing.Host
				mc.ExtraArgs = existing.ExtraArgs
			}
			c.Models[dm.Name] = mc
		} else {
			// Config priority: only add if not in config
			if !hasConfig {
				c.Models[dm.Name] = ModelConfig{
					Service:   dm.Service,
					ModelPath: dm.Path,
					Port:      c.VLLM.DefaultPort,
				}
			}
		}
	}
}
