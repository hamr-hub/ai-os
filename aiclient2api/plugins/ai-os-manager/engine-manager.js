import logger from '../../utils/logger.js';
import { backendClient } from './backend-client.js';

class EngineManagerService {
    constructor() {
        this.dataCache = null;
        this.configCache = null;
        this.lastFetchTime = null;
        this.pollingInterval = null;
        this.isPolling = false;
        this.refreshInterval = 5000;
    }

    async init() {
        logger.info('[EngineManager] Initializing...');
        this.startPolling();
    }

    async destroy() {
        this.stopPolling();
        logger.info('[EngineManager] Destroyed');
    }

    startPolling() {
        if (this.isPolling) return;
        this.isPolling = true;
        this.updateData();
        this.pollingInterval = setInterval(() => this.updateData(), this.refreshInterval);
    }

    stopPolling() {
        if (!this.isPolling) return;
        this.isPolling = false;
        if (this.pollingInterval) { clearInterval(this.pollingInterval); this.pollingInterval = null; }
    }

    async updateData() {
        try {
            const response = await backendClient.fetchWithFallback('/manage/engine/status');
            if (!response.ok) return;
            const result = await response.json();
            this.dataCache = this._normalizeResult(result);
            this.lastFetchTime = new Date().toISOString();
        } catch (error) {
            logger.error('[EngineManager] Error:', error.message);
        }
    }

    async updateConfig() {
        try {
            const response = await backendClient.fetchWithFallback('/engines/config');
            if (!response.ok) return;
            const result = await response.json();
            this.configCache = result;
        } catch (error) {
            logger.error('[EngineManager] Config fetch error:', error.message);
        }
    }

    _normalizeResult(result) {
        const field = result.current || result.primary || result.all?.[0] || result;
        return { ...field, timestamp: new Date().toISOString() };
    }

    getLatestData() {
        return { success: true, data: this.dataCache, timestamp: new Date().toISOString(), backendStatus: backendClient.getStatus() };
    }

    getConfig() {
        return { success: true, data: this.configCache, timestamp: new Date().toISOString(), backendStatus: backendClient.getStatus() };
    }

    async switchEngine(modelName, engineType, port) {
        try {
            const response = await backendClient.postWithFallback('/manage/engine/switch', {
                model_name: modelName,
                engine_type: engineType,
                port: port || 8000
            });
            const result = await response.json();
            return { success: response.ok, data: result, timestamp: new Date().toISOString() };
        } catch (error) {
            logger.error('[EngineManager] Switch error:', error.message);
            return { success: false, error: error.message };
        }
    }

    async updateEngineConfig(newConfig) {
        try {
            const response = await backendClient.fetchWithFallback('/engines/config', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(newConfig)
            });
            const result = await response.json();
            this.configCache = result;
            return { success: response.ok, data: result };
        } catch (error) {
            logger.error('[EngineManager] Config update error:', error.message);
            return { success: false, error: error.message };
        }
    }
}

const engineManager = new EngineManagerService();
export { EngineManagerService, engineManager };
export default engineManager;
