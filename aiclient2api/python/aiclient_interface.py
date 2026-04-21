import json
import os
import requests
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ProviderConfig:
    custom_name: str
    check_model_name: str
    check_health: bool
    concurrency_limit: int
    queue_limit: int
    openai_api_key: str
    openai_base_url: str
    uuid: str
    is_healthy: bool
    last_used: datetime
    usage_count: int
    error_count: int
    last_error_time: Optional[datetime]
    supported_models: List[str]
    not_supported_models: List[str]
    is_disabled: bool
    needs_refresh: bool
    refresh_count: int
    last_health_check_time: datetime
    last_health_check_model: str
    last_error_message: Optional[str]
    last_refresh_time: int
    _last_selection_seq: int


class AIClientInterface:
    def __init__(self, config_path: str = "/root/ai-os/aiclient2api/configs/provider_pools.json"):
        self.config_path = config_path
        self.providers: Dict[str, ProviderConfig] = {}
        self._load_config()

    def _load_config(self) -> None:
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            config_data = json.load(f)
        
        for provider_type, providers in config_data.items():
            for provider_data in providers:
                self.providers[provider_data['customName']] = ProviderConfig(
                    custom_name=provider_data['customName'],
                    check_model_name=provider_data['checkModelName'],
                    check_health=provider_data['checkHealth'],
                    concurrency_limit=provider_data['concurrencyLimit'],
                    queue_limit=provider_data['queueLimit'],
                    openai_api_key=provider_data['OPENAI_API_KEY'],
                    openai_base_url=provider_data['OPENAI_BASE_URL'],
                    uuid=provider_data['uuid'],
                    is_healthy=provider_data['isHealthy'],
                    last_used=datetime.fromisoformat(provider_data['lastUsed']),
                    usage_count=provider_data['usageCount'],
                    error_count=provider_data['errorCount'],
                    last_error_time=datetime.fromisoformat(provider_data['lastErrorTime']) if provider_data['lastErrorTime'] else None,
                    supported_models=provider_data['supportedModels'],
                    not_supported_models=provider_data['notSupportedModels'],
                    is_disabled=provider_data['isDisabled'],
                    needs_refresh=provider_data['needsRefresh'],
                    refresh_count=provider_data['refreshCount'],
                    last_health_check_time=datetime.fromisoformat(provider_data['lastHealthCheckTime']),
                    last_health_check_model=provider_data['lastHealthCheckModel'],
                    last_error_message=provider_data['lastErrorMessage'],
                    last_refresh_time=provider_data['lastRefreshTime'],
                    _last_selection_seq=provider_data['_lastSelectionSeq']
                )

    def get_provider(self, name: str) -> Optional[ProviderConfig]:
        return self.providers.get(name)

    def list_providers(self) -> List[str]:
        return list(self.providers.keys())

    def get_all_providers(self) -> List[ProviderConfig]:
        return list(self.providers.values())

    def get_healthy_providers(self) -> List[ProviderConfig]:
        return [p for p in self.providers.values() if p.is_healthy and not p.is_disabled]

    def get_provider_by_type(self, provider_type: str) -> List[ProviderConfig]:
        config_data = self._read_config()
        providers = []
        if provider_type in config_data:
            for provider_data in config_data[provider_type]:
                providers.append(self.get_provider(provider_data['customName']))
        return [p for p in providers if p is not None]

    def _read_config(self) -> Dict:
        with open(self.config_path, 'r') as f:
            return json.load(f)

    def update_provider_status(self, provider_name: str, **kwargs) -> bool:
        provider = self.get_provider(provider_name)
        if not provider:
            return False
        
        config_data = self._read_config()
        
        for provider_type, providers in config_data.items():
            for i, p in enumerate(providers):
                if p['customName'] == provider_name:
                    if 'isHealthy' in kwargs:
                        providers[i]['isHealthy'] = kwargs['isHealthy']
                    if 'lastUsed' in kwargs:
                        providers[i]['lastUsed'] = kwargs['lastUsed']
                    if 'usageCount' in kwargs:
                        providers[i]['usageCount'] = kwargs['usageCount']
                    if 'errorCount' in kwargs:
                        providers[i]['errorCount'] = kwargs['errorCount']
                    if 'lastErrorTime' in kwargs:
                        providers[i]['lastErrorTime'] = kwargs['lastErrorTime']
                    if 'lastErrorMessage' in kwargs:
                        providers[i]['lastErrorMessage'] = kwargs['lastErrorMessage']
                    if 'needsRefresh' in kwargs:
                        providers[i]['needsRefresh'] = kwargs['needsRefresh']
                    
                    with open(self.config_path, 'w') as f:
                        json.dump(config_data, f, indent=2)
                    
                    self._load_config()
                    return True
        
        return False

    def check_provider_health(self, provider_name: str) -> bool:
        provider = self.get_provider(provider_name)
        if not provider or provider.is_disabled:
            return False
        
        try:
            response = requests.get(
                f"{provider.openai_base_url}/v1/models",
                headers={"Authorization": f"Bearer {provider.openai_api_key}"},
                timeout=10
            )
            is_healthy = response.status_code == 200
            self.update_provider_status(
                provider_name,
                isHealthy=is_healthy,
                lastUsed=datetime.now().isoformat(),
                lastHealthCheckTime=datetime.now().isoformat()
            )
            return is_healthy
        except Exception as e:
            self.update_provider_status(
