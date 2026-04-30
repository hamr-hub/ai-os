import logger from '../../utils/logger.js';
import { backendClient } from '../ai-os-manager/backend-client.js';

class StatusService {
    constructor() {
        this.engineStatus = null;
        this.modelsData = null;
        this.runningModels = [];
        this.currentEngine = null;
        this.currentModel = null;
        this.lastFetchTime = null;
        this._pollingInterval = null;
        this._isPolling = false;
        this._refreshMs = 5000;
    }

    async init() {
        logger.info('[AI Monitor Status] Initialized');
    }

    async destroy() {
        this.stopPolling();
        logger.info('[AI Monitor Status] Destroyed');
    }

    startPolling() {
        if (this._isPolling) return;
        this._isPolling = true;
        this._fetchStatus();
        this._pollingInterval = setInterval(() => this._fetchStatus(), this._refreshMs);
    }

    stopPolling() {
        if (!this._isPolling) return;
        this._isPolling = false;
        if (this._pollingInterval) {
            clearInterval(this._pollingInterval);
            this._pollingInterval = null;
        }
    }

    async _fetchStatus() {
        try {
            await Promise.all([this._fetchEngineStatus(), this._fetchModels()]);
        } catch (error) {
            logger.error('[AI Monitor Status] Fetch error:', error.message);
        }
    }

    async _fetchEngineStatus() {
        try {
            const response = await backendClient.fetchWithFallback('/manage/engines/status');
            if (!response.ok) return;
            const result = await response.json();
            this.engineStatus = result;

            this.currentEngine = null;
            if (result.services && result.services.length > 0) {
                const running = result.services.find(s => s.status === 'running');
                if (running) {
                    this.currentEngine = running.engine_type || null;
                }
            }
            if (!this.currentEngine && result.engine_manager_mode) {
                this.currentEngine = result.engine_manager_mode;
            }
        } catch (error) {
            logger.error('[AI Monitor Status] Engine fetch error:', error.message);
        }
    }

    async _fetchModels() {
        try {
            const response = await backendClient.fetchWithFallback('/manage/models/aggregated');
            if (!response.ok) return;
            const result = await response.json();
            this.modelsData = result;
            this.runningModels = [];
            this.currentModel = result.current_model || null;

            if (result.groups) {
                for (const group of result.groups) {
                    for (const v of group.variants) {
                        if (v.running) {
                            this.runningModels.push({
                                name: v.name,
                                engine: v.backend_type || 'vllm',
                                port: v.port || null,
                                isCurrent: v.is_current || false,
                            });
                        }
                    }
                }
            }
            this.lastFetchTime = new Date().toISOString();
        } catch (error) {
            logger.error('[AI Monitor Status] Models fetch error:', error.message);
        }
    }

    getStatus() {
        if (!this._isPolling) this.startPolling();
        return {
            success: true,
            data: {
                currentEngine: this.currentEngine,
                currentModel: this.currentModel,
                runningModels: this.runningModels,
                engineStatus: this.engineStatus,
                modelsData: this.modelsData,
            },
            timestamp: this.lastFetchTime || new Date().toISOString(),
            backendStatus: backendClient.getStatus(),
        };
    }

    async switchModel(modelName, options = {}) {
        try {
            const body = {
                action: 'switch',
                model_name: modelName,
                set_as_default: false,
            };
            if (options.engine_type) body.engine_type = options.engine_type;
            if (options.port) body.port = options.port;

            const response = await backendClient.fetchWithFallback('/manage/switch/atomic', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            const result = await response.json();
            setTimeout(() => this._fetchStatus(), 2000);
            return { success: response.ok, data: result, timestamp: new Date().toISOString() };
        } catch (error) {
            logger.error('[AI Monitor Status] Switch model error:', error.message);
            return { success: false, error: error.message };
        }
    }

    async switchEngine(modelName, engineType, port) {
        try {
            const response = await backendClient.postWithFallback('/manage/engines/switch', {
                model_name: modelName,
                engine_type: engineType,
                port: port || 8000,
            });
            const result = await response.json();
            setTimeout(() => this._fetchStatus(), 2000);
            return { success: response.ok, data: result, timestamp: new Date().toISOString() };
        } catch (error) {
            logger.error('[AI Monitor Status] Switch engine error:', error.message);
            return { success: false, error: error.message };
        }
    }

    async getModelsList() {
        try {
            const response = await backendClient.fetchWithFallback('/manage/models/aggregated');
            const result = await response.json();
            const models = [];
            if (result.groups) {
                for (const group of result.groups) {
                    for (const v of group.variants) {
                        models.push({
                            name: v.name,
                            running: v.running || false,
                            engine: v.backend_type || 'vllm',
                            port: v.port || null,
                            isCurrent: v.is_current || false,
                            pathExists: v.path_exists !== false,
                            requiredMemory: v.required_memory || '',
                        });
                    }
                }
            }
            return { success: true, data: models, currentModel: result.current_model || null };
        } catch (error) {
            logger.error('[AI Monitor Status] Get models list error:', error.message);
            return { success: false, error: error.message };
        }
    }

    async getEnginesList() {
        try {
            const response = await backendClient.fetchWithFallback('/manage/engines/status');
            const result = await response.json();
            const engines = [];
            const engineTypes = ['vllm', 'sglang', 'llamacpp'];
            const engineLabels = { vllm: 'vLLM', sglang: 'SGLang', llamacpp: 'llama.cpp' };

            for (const type of engineTypes) {
                const service = result.services
                    ? result.services.find(s => s.engine_type === type && s.status === 'running')
                    : null;
                engines.push({
                    type,
                    label: engineLabels[type],
                    running: !!service,
                    port: service ? service.port : null,
                    model: service ? service.model : null,
                });
            }
            return { success: true, data: engines, currentEngine: this.currentEngine };
        } catch (error) {
            logger.error('[AI Monitor Status] Get engines list error:', error.message);
            return { success: false, error: error.message };
        }
    }
}

const statusService = new StatusService();
export { StatusService, statusService };
export default statusService;
