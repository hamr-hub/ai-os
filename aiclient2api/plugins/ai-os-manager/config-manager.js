import logger from '../../utils/logger.js';
import { backendClient } from './backend-client.js';

class ConfigManagerService {
    constructor() {
        this.globalConfigCache = null;
        this.vllmDefaultCache = null;
        this.defaultModelCache = null;
        this.engineConfigCache = null;
        this.lastFetchTime = null;
        this.pollingInterval = null;
        this.isPolling = false;
        this.refreshInterval = 30000;
    }

    async init() {
        logger.info('[ConfigManager] Initialized (polling deferred, starts on first data request)');
    }

    async destroy() {
        this.stopPolling();
        logger.info('[ConfigManager] Destroyed');
    }

    startPolling() {
        if (this.isPolling) return;
        this.isPolling = true;
        this.pollingInterval = setInterval(() => this.fetchAllConfigs(), this.refreshInterval);
    }

    stopPolling() {
        if (!this.isPolling) return;
        this.isPolling = false;
        if (this.pollingInterval) { clearInterval(this.pollingInterval); this.pollingInterval = null; }
    }

    async fetchAllConfigs() {
        try {
            await Promise.allSettled([
                this.fetchGlobalConfig(),
                this.fetchVLLMDefaultConfig(),
                this.fetchDefaultModel(),
            ]);
            this.lastFetchTime = new Date().toISOString();
        } catch (error) {
            logger.error('[ConfigManager] Fetch error:', error.message);
        }
    }

    async fetchGlobalConfig() {
        try {
            const response = await backendClient.fetchWithFallback('/manage/config/global');
            if (response.ok) {
                this.globalConfigCache = await response.json();
            }
        } catch (error) {
            logger.error('[ConfigManager] Global config fetch error:', error.message);
        }
    }

    async fetchVLLMDefaultConfig() {
        try {
            const response = await backendClient.fetchWithFallback('/manage/vllm/default-config');
            if (response.ok) {
                this.vllmDefaultCache = await response.json();
            }
        } catch (error) {
            logger.error('[ConfigManager] VLLM default config fetch error:', error.message);
        }
    }

    async fetchDefaultModel() {
        try {
            const response = await backendClient.fetchWithFallback('/manage/default-model');
            if (response.ok) {
                this.defaultModelCache = await response.json();
            }
        } catch (error) {
            logger.error('[ConfigManager] Default model fetch error:', error.message);
        }
    }

    getGlobalConfig() {
        if (!this.isPolling) this.startPolling();
        return { success: true, data: this.globalConfigCache, timestamp: new Date().toISOString(), backendStatus: backendClient.getStatus() };
    }

    getVLLMDefaultConfig() {
        return { success: true, data: this.vllmDefaultCache, timestamp: new Date().toISOString() };
    }

    getDefaultModel() {
        return { success: true, data: this.defaultModelCache, timestamp: new Date().toISOString() };
    }

    async updateGlobalConfig(newConfig) {
        try {
            const response = await backendClient.fetchWithFallback('/manage/config/global', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(newConfig)
            });
            const result = await response.json();
            this.globalConfigCache = result;
            return { success: response.ok, data: result };
        } catch (error) {
            return { success: false, error: error.message };
        }
    }

    async setDefaultModel(modelName) {
        try {
            const response = await backendClient.postWithFallback('/manage/default-model', { model: modelName });
            const result = await response.json();
            this.defaultModelCache = result;
            return { success: response.ok, data: result };
        } catch (error) {
            return { success: false, error: error.message };
        }
    }

    async clearDefaultModel() {
        try {
            const response = await backendClient.fetchWithFallback('/manage/default-model', { method: 'DELETE' });
            this.defaultModelCache = null;
            return { success: response.ok };
        } catch (error) {
            return { success: false, error: error.message };
        }
    }
}

const configManager = new ConfigManagerService();
export { ConfigManagerService, configManager };
export default configManager;
