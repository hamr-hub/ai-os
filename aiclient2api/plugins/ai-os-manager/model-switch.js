import logger from '../../utils/logger.js';
import { backendClient } from './backend-client.js';

class ModelSwitchService {
    constructor() {
        this.modelsCache = {};
        this.lastFetchTime = null;
        this.switchTasks = new Map();
        this.wsClients = new Set();
        this._cleanupInterval = setInterval(() => {
            const now = Date.now();
            for (const [id, task] of this.switchTasks) {
                if (task.endTime && (now - task.endTime > 600000)) {
                    this.switchTasks.delete(id);
                }
            }
        }, 120000);
    }

    registerWebSocket(ws) {
        this.wsClients.add(ws);
        ws.on('close', () => this.wsClients.delete(ws));
    }

    broadcastSwitchResult(taskId, result) {
        const message = JSON.stringify({
            type: 'model-switch-result',
            taskId,
            ...result,
            timestamp: new Date().toISOString()
        });
        this.wsClients.forEach(client => {
            if (client.readyState === 1) {
                client.send(message);
            }
        });
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
        clearInterval(this._cleanupInterval);
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
            const baseUrl = backendClient.getBaseUrl();
            const switchBody = {
                action: 'switch',
                model_name: modelName,
                set_as_default: false
            };
            if (options.engineType) switchBody.engine_type = options.engineType;
            if (options.port) switchBody.port = options.port;

            const response = await fetch(`${baseUrl}/manage/switch/atomic`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(switchBody),
                signal: AbortSignal.timeout(30000)
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
                        modelPath: variant.model_path || variant.path || '',
                        pathExists: variant.path_exists !== false,
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
                    modelPath: info.model_path || '',
                    pathExists: info.path_exists !== false,
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

    async switchModel(modelName, async = true, options = {}) {
        const mode = async ? 'warm' : 'cold';
        const taskId = `${Date.now()}-${Math.random().toString(36).substring(2, 8)}`;

        if (async) {
            this.switchTasks.set(taskId, {
                modelName,
                status: 'pending',
                startTime: Date.now()
            });

            setImmediate(() => {
                this._executeSwitch(taskId, modelName, mode, options).catch(err => {
                    logger.error('[Model Switch Service] Async switch task failed:', err.message);
                    this.switchTasks.set(taskId, {
                        modelName,
                        status: 'failed',
                        error: err.message,
                        endTime: Date.now()
                    });
                    this.broadcastSwitchResult(taskId, {
                        success: false,
                        error: err.message,
                        modelName
                    });
                });
            });

            logger.info(`[Model Switch Service] Async model switch started: ${modelName}, taskId: ${taskId}`);

            return {
                success: true,
                async: true,
                taskId,
                modelName,
                status: 'pending',
                message: 'Model switch started in background'
            };
        }

        return this._executeSwitch(taskId, modelName, mode, options);
    }

    async _executeSwitch(taskId, modelName, mode = 'warm', options = {}) {
        try {
            this.switchTasks.set(taskId, {
                modelName,
                status: 'switching',
                startTime: Date.now()
            });

            const baseUrl = backendClient.getBaseUrl();
            logger.info(`[Model Switch Service] Switching model (${mode}): ${modelName}, baseUrl: ${baseUrl}`);

            const response = await fetch(`${baseUrl}/manage/switch/atomic`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    action: 'switch',
                    model_name: modelName,
                    set_as_default: false
                }),
                signal: AbortSignal.timeout(30000)
            });

            logger.info(`[Model Switch Service] Switch response status: ${response.status}`);

            const data = await response.json();

            if (!response.ok) {
                const errorText = data.detail || data.error || data.message || 'Switch initiation failed';
                logger.error(`[Model Switch Service] Model switch initiation failed: ${response.status} - ${errorText}`);

                this.switchTasks.set(taskId, {
                    modelName,
                    status: 'failed',
                    error: errorText,
                    statusCode: response.status,
                    endTime: Date.now()
                });

                this.broadcastSwitchResult(taskId, {
                    success: false,
                    error: errorText,
                    statusCode: response.status,
                    modelName
                });

                return {
                    success: false,
                    error: errorText,
                    statusCode: response.status,
                    data: { modelName, status: 'failed' },
                    timestamp: new Date().toISOString(),
                    backendStatus: backendClient.getStatus()
                };
            }

            const sessionId = data.session_id;
            logger.info(`[Model Switch Service] Atomic switch started, session: ${sessionId}, polling status...`);

            const maxPollTime = 180000;
            const pollInterval = 3000;
            const startTime = Date.now();

            while (Date.now() - startTime < maxPollTime) {
                await new Promise(resolve => setTimeout(resolve, pollInterval));

                const statusResponse = await fetch(`${baseUrl}/manage/switch/status`, {
                    signal: AbortSignal.timeout(10000)
                });
                const statusData = await statusResponse.json();

                if (!statusData.is_switching && statusData.session && statusData.session.completed_successfully) {
                    await this.fetchModelsFromBackend();

                    this.switchTasks.set(taskId, {
                        modelName,
                        status: 'completed',
                        endTime: Date.now()
                    });

                    this.broadcastSwitchResult(taskId, {
                        success: true,
                        modelName,
                        mode
                    });

                    return {
                        success: true,
                        data: { modelName, status: 'completed', mode, sessionId },
                        timestamp: new Date().toISOString(),
                        backendStatus: backendClient.getStatus()
                    };
                }

                if (!statusData.is_switching && statusData.session && !statusData.session.completed_successfully) {
                    const errorMsg = statusData.session.error || statusData.session.rollback_reason || 'Switch failed';
                    logger.error(`[Model Switch Service] Model switch failed: ${errorMsg}`);

                    this.switchTasks.set(taskId, {
                        modelName,
                        status: 'failed',
                        error: errorMsg,
                        endTime: Date.now()
                    });

                    this.broadcastSwitchResult(taskId, {
                        success: false,
                        error: errorMsg,
                        modelName
                    });

                    return {
                        success: false,
                        error: errorMsg,
                        data: { modelName, status: 'failed', sessionId },
                        timestamp: new Date().toISOString(),
                        backendStatus: backendClient.getStatus()
                    };
                }
            }

            logger.error('[Model Switch Service] Model switch polling timed out');

            this.switchTasks.set(taskId, {
                modelName,
                status: 'failed',
                error: 'Switch polling timed out',
                endTime: Date.now()
            });

            this.broadcastSwitchResult(taskId, {
                success: false,
                error: 'Switch polling timed out',
                modelName
            });

            return {
                success: false,
                error: 'Switch polling timed out',
                data: { modelName, status: 'failed' },
                timestamp: new Date().toISOString(),
                backendStatus: backendClient.getStatus()
            };
        } catch (error) {
            logger.error('[Model Switch Service] Error switching model:', error.message);

            this.switchTasks.set(taskId, {
                modelName,
                status: 'failed',
                error: error.message,
                endTime: Date.now()
            });

            this.broadcastSwitchResult(taskId, {
                success: false,
                error: error.message,
                modelName
            });

            return {
                success: false,
                error: error.message,
                backendStatus: backendClient.getStatus()
            };
        }
    }

    getSwitchTaskStatus(taskId) {
        const task = this.switchTasks.get(taskId);
        if (!task) {
            return { success: false, error: 'Task not found', taskId };
        }
        return {
            success: true,
            taskId,
            modelName: task.modelName,
            status: task.status,
            startTime: task.startTime,
            endTime: task.endTime,
            error: task.error
        };
    }

    async startModel(modelName) {
        try {
            logger.info(`[Model Switch Service] Starting model via atomic switch: ${modelName}`);
            const baseUrl = backendClient.getBaseUrl();
            const response = await fetch(`${baseUrl}/manage/switch/atomic`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    action: 'start',
                    model_name: modelName,
                }),
                signal: AbortSignal.timeout(180000)
            });

            if (!response.ok) {
                const errorText = await response.text();
                logger.error(`[Model Switch Service] Model start failed: ${response.status} - ${errorText}`);
            }

            await this.fetchModelsFromBackend();

            return {
                success: response.ok,
                data: { modelName, status: response.ok ? 'completed' : 'failed' },
                timestamp: new Date().toISOString(),
                backendStatus: backendClient.getStatus()
            };
        } catch (error) {
            return { success: false, error: error.message, backendStatus: backendClient.getStatus() };
        }
    }

    async stopModel(modelName) {
        try {
            logger.info(`[Model Switch Service] Stopping model via atomic switch: ${modelName}`);
            const baseUrl = backendClient.getBaseUrl();
            const response = await fetch(`${baseUrl}/manage/switch/atomic`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    action: 'stop',
                    model_name: modelName,
                }),
                signal: AbortSignal.timeout(180000)
            });

            await this.fetchModelsFromBackend();

            return {
                success: response.ok,
                data: { modelName, status: response.ok ? 'completed' : 'failed' },
                timestamp: new Date().toISOString(),
                backendStatus: backendClient.getStatus()
            };
        } catch (error) {
            return { success: false, error: error.message, backendStatus: backendClient.getStatus() };
        }
    }

    async forceRestartModel(modelName, modelPath) {
        try {
            logger.info(`[Model Switch Service] Force restarting model via atomic switch: ${modelName}`);
            const response = await backendClient.fetchWithFallback('/manage/switch/atomic', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    action: 'switch',
                    model_name: modelName,
                    model_path: modelPath || null
                })
            });

            const result = await response.json();

            if (!response.ok) {
                const detail = result.detail;
                const errorMsg = typeof detail === 'object'
                    ? (detail.error || detail.message || JSON.stringify(detail))
                    : (detail || result.error || result.message || `Force restart failed with status ${response.status}`);
                return {
                    success: false,
                    error: errorMsg,
                    data: result,
                    timestamp: new Date().toISOString(),
                    backendStatus: backendClient.getStatus()
                };
            }

            await this.fetchModelsFromBackend();

            return {
                success: true,
                data: {
                    modelName,
                    sessionId: result.session_id,
                    status: result.status,
                    targetModel: result.target_model,
                    previousModel: result.previous_model,
                    message: result.message
                },
                timestamp: new Date().toISOString(),
                backendStatus: backendClient.getStatus()
            };
        } catch (error) {
            logger.error('[Model Switch Service] Error force restarting model:', error.message);
            return { success: false, error: error.message, backendStatus: backendClient.getStatus() };
        }
    }
}

const modelSwitchService = new ModelSwitchService();
export { ModelSwitchService, modelSwitchService };
export default modelSwitchService;
