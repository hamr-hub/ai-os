import logger from '../../utils/logger.js';

const GO_BACKEND_URL = process.env.GO_BACKEND_URL || 'http://localhost:35001';

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
            const response = await fetch(`${GO_BACKEND_URL}/manage/models`);
            if (!response.ok) throw new Error(`Go backend returned ${response.status}`);
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
            const response = await fetch(`${GO_BACKEND_URL}/manage/status`);
            if (!response.ok) throw new Error(`Go backend returned ${response.status}`);
            return await response.json();
        } catch (error) {
            logger.error('[Model Switch Service] Error fetching status:', error.message);
            return null;
        }
    }

    async getModelsList() {
        const models = await this.fetchModelsFromBackend();
        const modelArray = Object.entries(models).map(([name, info]) => ({
            name,
            running: info.running || false,
            backendType: info.backend_type || 'vllm',
            port: info.port || null,
            contextLength: info.context_length || null,
            description: info.description || '',
            activeRequests: info.active_requests || 0,
            preloaded: info.preloaded || false,
            status: info.running ? 'running' : 'stopped'
        }));
        return {
            success: true,
            data: modelArray,
            timestamp: this.lastFetchTime
        };
    }

    async switchModel(modelName) {
        try {
            const response = await fetch(`${GO_BACKEND_URL}/manage/models`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model: modelName, action: 'switch' })
            });
            if (!response.ok) throw new Error(`Go backend returned ${response.status}`);
            const result = await response.json();
            await this.fetchModelsFromBackend();
            return { success: true, data: { modelName, result }, timestamp: new Date().toISOString() };
        } catch (error) {
            logger.error('[Model Switch Service] Error switching model:', error.message);
            return { success: false, error: error.message };
        }
    }

    async startModel(modelName) {
        try {
            const response = await fetch(`${GO_BACKEND_URL}/manage/models/${encodeURIComponent(modelName)}/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
            });
            if (!response.ok) throw new Error(`Go backend returned ${response.status}`);
            const result = await response.json();
            await this.fetchModelsFromBackend();
            return { success: true, data: { modelName, action: 'start' }, timestamp: new Date().toISOString() };
        } catch (error) {
            logger.error('[Model Switch Service] Error starting model:', error.message);
            return { success: false, error: error.message };
        }
    }

    async stopModel(modelName) {
        try {
            const response = await fetch(`${GO_BACKEND_URL}/manage/models/${encodeURIComponent(modelName)}/stop`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
            });
            if (!response.ok) throw new Error(`Go backend returned ${response.status}`);
            const result = await response.json();
            await this.fetchModelsFromBackend();
            return { success: true, data: { modelName, action: 'stop' }, timestamp: new Date().toISOString() };
        } catch (error) {
            logger.error('[Model Switch Service] Error stopping model:', error.message);
            return { success: false, error: error.message };
        }
    }
}

const modelSwitchService = new ModelSwitchService();

export { ModelSwitchService, modelSwitchService };
export default modelSwitchService;
