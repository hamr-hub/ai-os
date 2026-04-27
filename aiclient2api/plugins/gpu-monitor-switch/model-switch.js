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
        logger.info(`[Model Switch Service] updateProviderCheckModel: configPath=${configPath}, modelName=${modelName}`);
        logger.info(`[Model Switch Service] process.cwd()=${process.cwd()}`);
        try {
            const raw = await fs.readFile(configPath, 'utf8');
            logger.info(`[Model Switch Service] Read config, length=${raw.length}`);
            const config = JSON.parse(raw);
            const providers = Array.isArray(config['openai-custom']) ? config['openai-custom'] : [];
            logger.info(`[Model Switch Service] Found ${providers.length} providers in config`);
            let updated = false;
            for (const provider of providers) {
                logger.info(`[Model Switch Service] Checking provider: customName=${provider?.customName}`);
                if (provider && provider.customName === 'app-controller') {
                    const oldModel = provider.checkModelName;
                    provider.checkModelName = modelName;
                    provider.lastHealthCheckModel = modelName;
                    provider.lastModelSwitchTime = new Date().toISOString();
                    updated = true;
                    logger.info(`[Model Switch Service] Updated checkModelName: ${oldModel} -> ${modelName}`);
                }
            }
            if (!updated) {
                logger.error('[Model Switch Service] app-controller provider not found in provider_pools.json');
                return { success: false, error: 'app-controller provider not found' };
            }
            const writeData = JSON.stringify(config, null, 2);
            await fs.writeFile(configPath, writeData, 'utf8');
            logger.info(`[Model Switch Service] Successfully wrote config to ${configPath}`);

            const verifyRaw = await fs.readFile(configPath, 'utf8');
            const verifyConfig = JSON.parse(verifyRaw);
            const verifyProvider = verifyConfig['openai-custom'].find(p => p.customName === 'app-controller');
            if (verifyProvider && verifyProvider.checkModelName === modelName) {
                logger.info(`[Model Switch Service] Verification: checkModelName=${verifyProvider.checkModelName} - OK`);
                return { success: true, modelName };
            } else {
                logger.error('[Model Switch Service] Verification failed after write');
                return { success: false, error: 'verification failed' };
            }
        } catch (error) {
            logger.error('[Model Switch Service] Error updating provider check model:', error.message);
            logger.error('[Model Switch Service] Stack:', error.stack);
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
                
                const providerUpdate = await this.updateProviderCheckModel(modelName);
                logger.info('[Model Switch Service] Config update after failed switch:', JSON.stringify(providerUpdate));
                
                return {
                    success: false,
                    error: result.error || result.message || `Switch failed with status ${response.status}`,
                    providerUpdate,
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
            
            const providerUpdate = await this.updateProviderCheckModel(modelName);
            logger.info('[Model Switch Service] Config update after exception:', JSON.stringify(providerUpdate));
            
            return { success: false, error: error.message, providerUpdate, backendStatus: backendClient.getStatus() };
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
