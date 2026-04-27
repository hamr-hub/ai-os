import logger from '../../utils/logger.js';
import { backendClient, GO_BACKEND_URL, PYTHON_BACKEND_URL } from './backend-client.js';

class ModelSwitchService {
    constructor() {
        this.modelsCache = {};
        this.lastFetchTime = null;
    }

    async init() {
        logger.info('[Model Switch Service] Initializing model switch service (with Go/Python fallback)...');
        await this.fetchModelsFromBackend();
    }

    async destroy() {
        logger.info('[Model Switch Service] Model switch service destroyed');
    }

    async fetchModelsFromBackend() {
        try {
            const response = await backendClient.fetchWithFallback('/manage/models');
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
            const response = await backendClient.fetchWithFallback('/manage/monitor/all');
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
                backendType: info.backend_type || info.service || 'vllm',
                port: info.port || null,
                description: info.description || '',
                activeRequests: info.active_requests || 0,
                preloaded: info.preloaded || false,
                status: info.running ? 'running' : 'stopped'
            };
        });
        return { success: true, data: modelArray, timestamp: this.lastFetchTime, backendStatus: backendClient.getStatus() };
    }

    async switchModel(modelName) {
        try {
            const response = await backendClient.postWithFallback(
                `/manage/models/${encodeURIComponent(modelName)}/switch`,
                {}
            );
            const result = await response.json();
            await this.fetchModelsFromBackend();
            return { success: true, data: { modelName: modelName, result: result }, timestamp: new Date().toISOString(), backendStatus: backendClient.getStatus() };
        } catch (error) {
            logger.error('[Model Switch Service] Error switching model:', error.message);
            return { success: false, error: error.message, backendStatus: backendClient.getStatus() };
        }
    }

    async startModel(modelName) {
        try {
            const response = await backendClient.postWithFallback(
                `/manage/models/${encodeURIComponent(modelName)}/start`,
                {}
            );
            const result = await response.json();
            await this.fetchModelsFromBackend();
            return { success: true, data: { modelName: modelName, action: 'start' }, timestamp: new Date().toISOString(), backendStatus: backendClient.getStatus() };
        } catch (error) {
            return { success: false, error: error.message, backendStatus: backendClient.getStatus() };
        }
    }

    async stopModel(modelName) {
        try {
            const response = await backendClient.postWithFallback(
                `/manage/models/${encodeURIComponent(modelName)}/stop`,
                {}
            );
            const result = await response.json();
            await this.fetchModelsFromBackend();
            return { success: true, data: { modelName: modelName, action: 'stop' }, timestamp: new Date().toISOString(), backendStatus: backendClient.getStatus() };
        } catch (error) {
            return { success: false, error: error.message, backendStatus: backendClient.getStatus() };
        }
    }
}

const modelSwitchService = new ModelSwitchService();
export { ModelSwitchService, modelSwitchService };
export default modelSwitchService;
