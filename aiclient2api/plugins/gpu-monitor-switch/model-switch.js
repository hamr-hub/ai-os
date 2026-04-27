import logger from '../../utils/logger.js';

const GO_BACKEND_URL = process.env.GO_BACKEND_URL || 'http://go-vllm-api-go-vllm-api-1:35001';

class ModelSwitchService {
    constructor() {
        this.modelsCache = {};
        this.lastFetchTime = null;
    }

    async init() {
        logger.info('[Model Switch Service] Initializing model switch service (Go backend)...');
        await this.fetchModelsFromBackend();
    }

    async destroy() {
        logger.info('[Model Switch Service] Model switch service destroyed');
    }

    async fetchModelsFromBackend() {
        try {
            const response = await fetch(GO_BACKEND_URL + '/manage/models');
            this.modelsCache = await response.json();
            this.lastFetchTime = new Date().toISOString();
            return this.modelsCache;
        } catch (error) {
            logger.error('[Model Switch Service] Error fetching models:', error.message);
            return {};
        }
    }

    async getStatusFromBackend() {
        try {
            const response = await fetch(GO_BACKEND_URL + '/manage/status');
            return await response.json();
        } catch (error) {
            logger.error('[Model Switch Service] Error fetching status:', error.message);
            return null;
        }
    }

    async getModelsList() {
        const models = await this.fetchModelsFromBackend();
        const modelArray = Object.entries(models).map(function(entry) {
            var name = entry[0];
            var info = entry[1];
            return {
                name: name,
                running: info.running || false,
                backendType: info.backend_type || 'vllm',
                port: info.port || null,
                description: info.description || '',
                activeRequests: info.active_requests || 0,
                preloaded: info.preloaded || false,
                status: info.running ? 'running' : 'stopped'
            };
        });
        return { success: true, data: modelArray, timestamp: this.lastFetchTime };
    }

    async switchModel(modelName) {
        try {
            const response = await fetch(GO_BACKEND_URL + '/manage/models', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model: modelName, action: 'switch' })
            });
            const result = await response.json();
            await this.fetchModelsFromBackend();
            return { success: true, data: { modelName: modelName, result: result }, timestamp: new Date().toISOString() };
        } catch (error) {
            logger.error('[Model Switch Service] Error switching model:', error.message);
            return { success: false, error: error.message };
        }
    }

    async startModel(modelName) {
        try {
            const response = await fetch(GO_BACKEND_URL + '/manage/models/' + encodeURIComponent(modelName) + '/start', {
                method: 'POST', headers: { 'Content-Type': 'application/json' }
            });
            const result = await response.json();
            await this.fetchModelsFromBackend();
            return { success: true, data: { modelName: modelName, action: 'start' }, timestamp: new Date().toISOString() };
        } catch (error) {
            return { success: false, error: error.message };
        }
    }

    async stopModel(modelName) {
        try {
            const response = await fetch(GO_BACKEND_URL + '/manage/models/' + encodeURIComponent(modelName) + '/stop', {
                method: 'POST', headers: { 'Content-Type': 'application/json' }
            });
            const result = await response.json();
            await this.fetchModelsFromBackend();
            return { success: true, data: { modelName: modelName, action: 'stop' }, timestamp: new Date().toISOString() };
        } catch (error) {
            return { success: false, error: error.message };
        }
    }
}

const modelSwitchService = new ModelSwitchService();
export { ModelSwitchService, modelSwitchService };
export default modelSwitchService;
