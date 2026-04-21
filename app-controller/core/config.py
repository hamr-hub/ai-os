from pydantic import BaseModel, Field, validator, ValidationError
from typing import Optional, Dict, List, Any
import yaml
import os

class ModelConfig(BaseModel):
    service: str
    port: int = Field(ge=1, le=65535)
    required_memory: str = "8GB"
    preload: bool = False
    keep_alive: bool = True
    model_path: Optional[str] = None

    @validator('required_memory')
    def validate_memory_format(cls, v):
        if not v:
            return "8GB"
        v = str(v).strip().upper()
        valid_suffixes = ['B', 'KB', 'MB', 'GB', 'TB']
        has_valid_suffix = any(v.endswith(suffix) for suffix in valid_suffixes)
        if not has_valid_suffix:
            raise ValueError(f"Invalid memory format: {v}. Use format like '8GB', '16GB', etc.")
        return v

class QueueConfig(BaseModel):
    max_length: int = Field(ge=1, le=1000, default=100)
    poll_interval: float = Field(ge=0.1, le=10.0, default=0.5)
    wait_timeout: int = Field(ge=1, le=300, default=30)

class PriorityConfig(BaseModel):
    default: str = "normal"
    enabled: bool = True

class RecoveryConfig(BaseModel):
    max_restart_attempts: int = Field(ge=1, le=10, default=3)
    restart_cooldown: int = Field(ge=1, le=300, default=60)
    watchdog_check_interval: int = Field(ge=1, le=60, default=5)

class SettingsConfig(BaseModel):
    concurrency_limit: int = Field(ge=1, le=100, default=4)
    min_available_memory: str = "2GB"
    request_timeout: int = Field(ge=10, le=300, default=60)
    model_start_timeout: int = Field(ge=10, le=300, default=60)
    preload_timeout: int = Field(ge=30, le=600, default=120)
    idle_timeout: int = Field(ge=60, le=3600, default=300)
    memory_flush_interval: int = Field(ge=60, le=3600, default=300)
    memory_cleanup_delay: int = Field(ge=1, le=30, default=3)
    gpu_memory_utilization: float = Field(ge=0.5, le=0.99, default=0.9)
    default_memory_strategy: str = "balanced"
    
    queue: QueueConfig = QueueConfig()
    priority: PriorityConfig = PriorityConfig()
    recovery: RecoveryConfig = RecoveryConfig()

    @validator('default_memory_strategy')
    def validate_memory_strategy(cls, v):
        valid_strategies = ["conservative", "balanced", "aggressive"]
        if v not in valid_strategies:
            raise ValueError(f"Invalid memory strategy: {v}. Must be one of {valid_strategies}")
        return v

class AppConfig(BaseModel):
    models: Dict[str, ModelConfig] = {}
    settings: SettingsConfig = SettingsConfig()

    def get_model(self, model_name: str) -> Optional[ModelConfig]:
        return self.models.get(model_name)

    def get_model_port(self, model_name: str) -> Optional[int]:
        model = self.get_model(model_name)
        return model.port if model else None

    def get_model_service(self, model_name: str) -> Optional[str]:
        model = self.get_model(model_name)
        return model.service if model else None

    def get_concurrency_limit(self) -> int:
        return self.settings.concurrency_limit

    def get_min_available_memory(self) -> str:
        return self.settings.min_available_memory

def parse_memory_size(size_str: str) -> int:
    if not size_str:
        return 0
    
    size_str = str(size_str).strip().upper()
    multipliers = {
        'TB': 1024 ** 4,
        'GB': 1024 ** 3,
        'MB': 1024 ** 2,
        'KB': 1024,
        'B': 1
    }
    
    for suffix, multiplier in multipliers.items():
        if size_str.endswith(suffix):
            num_str = size_str[:-len(suffix)].strip()
            if num_str:
                try:
                    num = float(num_str)
                    return int(num * multiplier)
                except ValueError:
                    pass
            break
    
    try:
        return int(size_str)
    except ValueError:
        return 0

def load_config(config_path: str) -> AppConfig:
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                raw_config = yaml.safe_load(f)
            return AppConfig(**raw_config)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in config file: {e}")
        except ValidationError as e:
            raise ValueError(f"Config validation failed: {e}")
    
    return AppConfig()

def validate_config(config: AppConfig) -> List[str]:
    errors = []
    
    if not config.models:
        errors.append("No models configured")
    
    for model_name, model_config in config.models.items():
        if not model_config.service:
            errors.append(f"Model '{model_name}' has no service defined")
        if model_config.port < 1 or model_config.port > 65535:
            errors.append(f"Model '{model_name}' has invalid port: {model_config.port}")
    
    if config.settings.concurrency_limit < 1:
        errors.append("Concurrency limit must be at least 1")
    
    return errors