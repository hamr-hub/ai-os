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
            const response = await backendClient.fetchWithFallback('/manage/models/aggregated');
            const result = await response.json();
            this.modelsCache = result;
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
                    provider.isHealthy = true;
                    provider.errorCount = 0;
                    provider.lastErrorTime = null;
                    provider.lastErrorMessage = null;
                    updated = true;
                    logger.info(`[Model Switch Service] Updated checkModelName: ${oldModel} -> ${modelName}, reset health status`);
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
            } else {
                logger.error('[Model Switch Service] Verification failed after write');
                return { success: false, error: 'verification failed' };
            }

            await this._updateInMemoryProviderStatus(modelName);

            return { success: true, modelName };
        } catch (error) {
            logger.error('[Model Switch Service] Error updating provider check model:', error.message);
            logger.error('[Model Switch Service] Stack:', error.stack);
            return { success: false, error: error.message };
        }
    }

    async _updateInMemoryProviderStatus(modelName) {
        try {
            const { getProviderPoolManager } = await import('../../services/service-manager.js');
            const poolManager = getProviderPoolManager();
            if (!poolManager || !poolManager.providerStatus) {
                logger.warn('[Model Switch Service] ProviderPoolManager not available, skipping in-memory update');
                return;
            }

            const providerType = 'openai-custom';
            const providers = poolManager.providerStatus[providerType];
            if (!Array.isArray(providers)) {
                logger.warn(`[Model Switch Service] No providerStatus for ${providerType}`);
                return;
            }

            for (const provider of providers) {
                if (provider.config && provider.config.customName === 'app-controller') {
                    const oldModel = provider.config.checkModelName;
                    provider.config.checkModelName = modelName;
                    provider.config.lastHealthCheckModel = modelName;
                    provider.config.lastModelSwitchTime = new Date().toISOString();
                    provider.config.isHealthy = true;
                    provider.config.errorCount = 0;
                    provider.config.lastErrorTime = null;
                    provider.config.lastErrorMessage = null;
                    if (provider.healthState) {
                        provider.healthState.isHealthy = true;
                        provider.healthState.errorCount = 0;
                        provider.healthState.lastErrorTime = null;
                        provider.healthState.lastErrorMessage = null;
                    }
                    logger.info(`[Model Switch Service] Updated in-memory checkModelName: ${oldModel} -> ${modelName}, reset health status`);
                }
            }

            if (poolManager.providerPools && Array.isArray(poolManager.providerPools[providerType])) {
                for (const provider of poolManager.providerPools[providerType]) {
                    if (provider.customName === 'app-controller') {
                        provider.checkModelName = modelName;
                        provider.lastHealthCheckModel = modelName;
                        provider.lastModelSwitchTime = new Date().toISOString();
                        provider.isHealthy = true;
                        provider.errorCount = 0;
                        provider.lastErrorTime = null;
                        provider.lastErrorMessage = null;
                        logger.info(`[Model Switch Service] Updated in-memory providerPools checkModelName -> ${modelName}, reset health status`);
                    }
                }
            }

            logger.info('[Model Switch Service] In-memory provider status updated successfully');
        } catch (error) {
            logger.warn('[Model Switch Service] Failed to update in-memory provider status:', error.message);
        }
    }

    async getModelsList() {
        const result = await this.fetchModelsFromBackend();
        const modelArray = [];

        if (result.groups) {
            for (const group of result.groups) {
                for (const variant of group.variants) {
                    modelArray.push({
                        name: variant.name,
                        baseName: group.base_name,
                        running: variant.running || false,
                        backendType: variant.backend_type || variant.service || 'vllm',
                        port: variant.port || null,
                        description: variant.description || '',
                        requiredMemory: variant.required_memory || '',
                        memoryGB: variant.required_memory_gb || 0,
                        sizeMB: variant.size_mb || 0,
                        multimodal: variant.multimodal || false,
                        vllmConfig: variant.vllm_config || null,
                        isCurrent: variant.is_current || false,
                        status: variant.running ? 'running' : 'stopped',
                        variantCount: group.variant_count,
                        groupSizeMB: group.total_size_mb
                    });
                }
            }
        } else {
            const models = result.data || result;
            for (const [name, info] of Object.entries(models)) {
                modelArray.push({
                    name: name,
                    running: info.running || false,
                    backendType: info.backend_type || info.service || 'vllm',
                    port: info.port || null,
                    description: info.description || '',
                    status: info.running ? 'running' : 'stopped'
                });
            }
        }

        return {
            success: true,
            data: modelArray,
            groups: result.groups || [],
            totalGroups: result.total_groups || 0,
            totalVariants: result.total_variants || modelArray.length,
            currentModel: result.current_model || null,
            timestamp: this.lastFetchTime,
            backendStatus: backendClient.getStatus()
        };
    }

    async getAggregatedModels(refresh = false) {
        try {
            const response = await backendClient.fetchWithFallback(`/manage/models/aggregated${refresh ? '?refresh=true' : ''}`);
            const data = await response.json();
            return { success: true, data: data, timestamp: new Date().toISOString() };
        } catch (error) {
            logger.error('[Model Switch Service] Error fetching aggregated models:', error.message);
            return { success: false, error: error.message };
        }
    }

    async getModelVLLMParams(modelName) {
        try {
            const response = await backendClient.fetchWithFallback(`/manage/models/${encodeURIComponent(modelName)}/vllm-params`);
            const data = await response.json();
            return { success: true, data: data, timestamp: new Date().toISOString() };
        } catch (error) {
            logger.error('[Model Switch Service] Error fetching vLLM params for', modelName, ':', error.message);
            return { success: false, error: error.message };
        }
    }

    async updateModelVLLMParams(modelName, vllmParams) {
        try {
            const baseUrl = backendClient.getBaseUrl();
            const url = `${baseUrl}/manage/models/${encodeURIComponent(modelName)}/vllm-params`;
            const response = await fetch(url, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ vllm_params: vllmParams }),
                signal: AbortSignal.timeout(30000)
            });
            const data = await response.json();
            if (!response.ok) {
                return { success: false, error: data.error || data.message || `Update failed with status ${response.status}` };
            }
            return { success: true, data: data, timestamp: new Date().toISOString() };
        } catch (error) {
            logger.error('[Model Switch Service] Error updating vLLM params for', modelName, ':', error.message);
            return { success: false, error: error.message };
        }
    }

    async getSwitchStatus() {
        try {
            const response = await backendClient.fetchWithFallback('/manage/switch/status');
            return await response.json();
        } catch (error) {
            logger.error('[Model Switch Service] Error fetching switch status:', error.message);
            return {
                is_switching: false,
                session: null,
                error: error.message,
                timestamp: new Date().toISOString()
            };
        }
    }

    async cancelSwitch() {
        try {
            const response = await backendClient.fetchWithFallback('/manage/switch/cancel', {
                method: 'DELETE'
            });
            return await response.json();
        } catch (error) {
            logger.error('[Model Switch Service] Error cancelling switch:', error.message);
            return { success: false, error: error.message };
        }
    }

    async finalizeAtomicSwitch(session) {
        if (!session || !session.completed_successfully || session.overall_phase !== 'completed') {
            return {
                success: false,
                error: session?.rollback_reason || session?.error || 'switch not completed'
            };
        }

        const modelName = session.target_model;
        const warmup = await this.warmupModel(modelName);
        const providerUpdate = await this.updateProviderCheckModel(modelName);
        await this.fetchModelsFromBackend();

        return {
            success: Boolean(warmup?.success && providerUpdate?.success),
            data: {
                modelName,
                warmup,
                providerUpdate,
                session,
            },
            timestamp: new Date().toISOString(),
            backendStatus: backendClient.getStatus()
        };
    }

    async switchModel(modelName) {
        try {
            logger.info(`[Model Switch Service] Starting atomic model switch to: ${modelName}`);
            const response = await backendClient.postWithFallback(
                '/manage/switch/atomic',
                {
                    model_name: modelName,
                    set_as_default: true,
                }
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
                    error: result.error || result.message || result.detail?.error || `Switch failed with status ${response.status}`,
                    backendStatus: backendClient.getStatus()
                };
            }

            await this.fetchModelsFromBackend();

            return {
                success: true,
                data: {
                    modelName,
                    sessionId: result.session_id,
                    targetModel: result.target_model,
                    previousModel: result.previous_model,
                    status: result.status,
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
