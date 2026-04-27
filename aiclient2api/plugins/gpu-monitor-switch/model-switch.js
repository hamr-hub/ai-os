import logger from '../../utils/logger.js';
import { backendClient, GO_BACKEND_URL, PYTHON_BACKEND_URL } from './backend-client.js';
import fs from 'fs/promises';
import pathModule from 'path';

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

    async warmupModel(modelName) {
        try {
            const response = await fetch(`${backendClient.getBaseUrl()}/v1/chat/completions`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    model: modelName,
                    messages: [{ role: 'user', content: 'hi' }],
                    max_tokens: 8,
                    temperature: 0
                }),
                signal: AbortSignal.timeout(45000)
            });
            const text = await response.text();
            let data = null;
            try {
                data = text ? JSON.parse(text) : null;
            } catch {
                data = null;
            }
            return {
                success: response.ok,
                status: response.status,
                data,
                raw: text.slice(0, 500)
            };
        } catch (error) {
            logger.error('[Model Switch Service] Error warming model:', error.message);
            return { success: false, error: error.message };
        }
    }

    async updateProviderCheckModel(modelName) {
        const configPath = pathModule.resolve(process.cwd(), 'configs', 'provider_pools.json');
        try {
            const raw = await fs.readFile(configPath, 'utf8');
            const config = JSON.parse(raw);
            const providers = Array.isArray(config['openai-custom']) ? config['openai-custom'] : [];
            let updated = false;
            providers.forEach((provider) => {
                if (provider && provider.customName === 'app-controller') {
                    provider.checkModelName = modelName;
                    provider.lastHealthCheckModel = modelName;
                    provider.lastModelSwitchTime = new Date().toISOString();
                    updated = true;
                }
            });
            if (!updated) {
                return { success: false, error: 'app-controller provider not found' };
            }
            await fs.writeFile(configPath, JSON.stringify(config, null, 2), 'utf8');
            return { success: true, modelName };
        } catch (error) {
            logger.error('[Model Switch Service] Error updating provider check model:', error.message);
            return { success: false, error: error.message };
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
            logger.info(`[Model Switch Service] Starting model switch to: ${modelName}`);
            const response = await backendClient.postWithFallback(
                `/manage/models/${encodeURIComponent(modelName)}/switch`,
                {}
            );
            let result;
            try {
                result = await response.json();
            } catch (e) {
                logger.warn('[Model Switch Service] Failed to parse switch result:', e.message);
                result = { status: 'unknown', raw: await response.text().catch(() => '') };
            }

            if (!response.ok) {
                logger.error('[Model Switch Service] Model switch returned error:', result);
                return {
                    success: false,
                    error: result.error || result.message || `Switch failed with status ${response.status}`,
                    backendStatus: backendClient.getStatus()
                };
            }

            logger.info(`[Model Switch Service] Model switch completed for: ${modelName}, warming up...`);
            const warmup = await this.warmupModel(modelName);

            const providerUpdate = await this.updateProviderCheckModel(modelName);

            await this.fetchModelsFromBackend();

            return {
                success: true,
                data: {
                    modelName: modelName,
                    result: result,
                    warmup,
                    providerUpdate
                },
                timestamp: new Date().toISOString(),
                backendStatus: backendClient.getStatus()
            };
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
