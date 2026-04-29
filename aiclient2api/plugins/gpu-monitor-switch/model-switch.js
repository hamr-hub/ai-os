import logger from '../../utils/logger.js';
import { backendClient } from './backend-client.js';

class ModelSwitchService {
    constructor() {
        this.modelsCache = {};
        this.lastFetchTime = null;
    }

    _extractError(result, fallbackMessage) {
        if (!result) return fallbackMessage;
        const detail = result.detail;
        if (typeof detail === 'string' && detail) return detail;
        if (detail && typeof detail === 'object') {
            return detail.error || detail.message || detail.rollback_reason || fallbackMessage;
        }
        return result.error || result.message || fallbackMessage;
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
                        sizeBytes: (variant.size_mb || 0) * 1024 * 1024,
                        multimodal: variant.multimodal || false,
                        vllmConfig: variant.vllm_config || null,
                        isCurrent: variant.is_current || false,
                        status: variant.running ? 'running' : 'stopped',
                        variantCount: group.variant_count,
                        groupSizeMB: group.total_size_mb,
                        groupSizeBytes: (group.total_size_mb || 0) * 1024 * 1024
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
                    status: info.running ? 'running' : 'stopped',
                    sizeMB: info.size_mb || 0,
                    sizeBytes: (info.size_mb || 0) * 1024 * 1024,
                    vllmConfig: info.vllm_config || null
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

    async switchModel(modelName) {
        try {
            logger.info(`[Model Switch Service] Starting atomic model switch to: ${modelName}`);
            const response = await backendClient.postWithFallback(
                '/manage/switch/atomic',
                {
                    action: 'switch',
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
                    error: this._extractError(result, `Switch failed with status ${response.status}`),
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
                '/manage/switch/atomic',
                {
                    action: 'start',
                    model_name: modelName,
                }
            );
            const result = await response.json();
            await this.fetchModelsFromBackend();
            return {
                success: response.ok,
                data: {
                    modelName,
                    sessionId: result.session_id,
                    targetModel: result.target_model,
                    previousModel: result.previous_model,
                    status: result.status,
                    action: result.action || 'start',
                },
                error: response.ok ? undefined : this._extractError(result, `Start failed with status ${response.status}`),
                timestamp: new Date().toISOString(),
                backendStatus: backendClient.getStatus()
            };
        } catch (error) {
            return { success: false, error: error.message, backendStatus: backendClient.getStatus() };
        }
    }

    async stopModel(modelName) {
        try {
            const response = await backendClient.postWithFallback(
                '/manage/switch/atomic',
                {
                    action: 'stop',
                    model_name: modelName,
                }
            );
            const result = await response.json();
            await this.fetchModelsFromBackend();
            return {
                success: response.ok,
                data: {
                    modelName,
                    sessionId: result.session_id,
                    targetModel: result.target_model,
                    previousModel: result.previous_model,
                    status: result.status,
                    action: result.action || 'stop',
                },
                error: response.ok ? undefined : this._extractError(result, `Stop failed with status ${response.status}`),
                timestamp: new Date().toISOString(),
                backendStatus: backendClient.getStatus()
            };
        } catch (error) {
            return { success: false, error: error.message, backendStatus: backendClient.getStatus() };
        }
    }
}

const modelSwitchService = new ModelSwitchService();
export { ModelSwitchService, modelSwitchService };
export default modelSwitchService;
