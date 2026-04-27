import fs from 'fs/promises';
import { existsSync } from 'fs';
import path from 'path';
import logger from '../../utils/logger.js';

const POOLS_CONFIG_FILE = path.join(process.cwd(), 'configs', 'provider_pools.json');

class ModelSwitchService {
    constructor() {
        this.poolsConfig = null;
        this.currentModels = new Map();
    }

    async init() {
        logger.info('[Model Switch Service] Initializing model switch service...');
        await this.loadPoolsConfig();
    }

    async destroy() {
        logger.info('[Model Switch Service] Model switch service destroyed');
    }

    async loadPoolsConfig() {
        try {
            if (!existsSync(POOLS_CONFIG_FILE)) {
                logger.warn('[Model Switch Service] Provider pools config file not found');
                this.poolsConfig = {};
                return;
            }
            
            const content = await fs.readFile(POOLS_CONFIG_FILE, 'utf8');
            this.poolsConfig = JSON.parse(content);
            logger.info('[Model Switch Service] Loaded provider pools config');
        } catch (error) {
            logger.error('[Model Switch Service] Failed to load provider pools config:', error.message);
            this.poolsConfig = {};
        }
    }

    async savePoolsConfig() {
        try {
            const dir = path.dirname(POOLS_CONFIG_FILE);
            if (!existsSync(dir)) {
                await fs.mkdir(dir, { recursive: true });
            }
            await fs.writeFile(POOLS_CONFIG_FILE, JSON.stringify(this.poolsConfig, null, 2), 'utf8');
            logger.info('[Model Switch Service] Saved provider pools config');
        } catch (error) {
            logger.error('[Model Switch Service] Failed to save provider pools config:', error.message);
            throw error;
        }
    }

    getProviderPools() {
        const providers = [];
        
        for (const [providerName, pools] of Object.entries(this.poolsConfig)) {
            if (!Array.isArray(pools)) continue;
            
            pools.forEach(pool => {
                providers.push({
                    providerName,
                    customName: pool.customName || pool.OPENAI_BASE_URL || 'Unknown',
                    uuid: pool.uuid,
                    baseUrl: pool.OPENAI_BASE_URL,
                    currentModel: pool.checkModelName,
                    isHealthy: pool.isHealthy,
                    isDisabled: pool.isDisabled,
                    lastHealthCheck: pool.lastHealthCheckTime,
                    usageCount: pool.usageCount || 0,
                    errorCount: pool.errorCount || 0,
                    supportedModels: pool.supportedModels || [],
                    notSupportedModels: pool.notSupportedModels || []
                });
            });
        }
        
        return {
            success: true,
            data: providers,
            timestamp: new Date().toISOString()
        };
    }

    async switchModel(providerName, customName, newModel) {
        try {
            if (!this.poolsConfig[providerName]) {
                return {
                    success: false,
                    error: `Provider "${providerName}" not found`
                };
            }
            
            const pools = this.poolsConfig[providerName];
            let targetPool = null;
            let targetIndex = -1;
            
            for (let i = 0; i < pools.length; i++) {
                if (customName) {
                    if (pools[i].customName === customName || pools[i].uuid === customName) {
                        targetPool = pools[i];
                        targetIndex = i;
                        break;
                    }
                }
            }
            
            if (!targetPool) {
                return {
                    success: false,
                    error: `Provider instance "${customName}" not found`
                };
            }
            
            const oldModel = targetPool.checkModelName;
            targetPool.checkModelName = newModel;
            targetPool.needsRefresh = true;
            targetPool.lastModelSwitchTime = new Date().toISOString();
            
            await this.savePoolsConfig();
            
            logger.info(`[Model Switch Service] Switched model for ${customName}: ${oldModel} -> ${newModel}`);
            
            return {
                success: true,
                data: {
                    providerName,
                    customName,
                    oldModel,
                    newModel,
                    timestamp: new Date().toISOString()
                }
            };
        } catch (error) {
            logger.error('[Model Switch Service] Failed to switch model:', error.message);
            return {
                success: false,
                error: error.message
            };
        }
    }

    async getAvailableModels(providerName, customName) {
        try {
            if (!this.poolsConfig[providerName]) {
                return {
                    success: false,
                    error: `Provider "${providerName}" not found`
                };
            }
            
            const pools = this.poolsConfig[providerName];
            let targetPool = null;
            
            for (const pool of pools) {
                if (customName) {
                    if (pool.customName === customName || pool.uuid === customName) {
                        targetPool = pool;
                        break;
                    }
                }
            }
            
            if (!targetPool) {
                return {
                    success: false,
                    error: `Provider instance "${customName}" not found`
                };
            }
            
            return {
                success: true,
                data: {
                    currentModel: targetPool.checkModelName,
                    supportedModels: targetPool.supportedModels || [],
                    notSupportedModels: targetPool.notSupportedModels || []
                }
            };
        } catch (error) {
            logger.error('[Model Switch Service] Failed to get available models:', error.message);
            return {
                success: false,
                error: error.message
            };
        }
    }

    async refreshProvider(providerName, customName) {
        try {
            if (!this.poolsConfig[providerName]) {
                return {
                    success: false,
                    error: `Provider "${providerName}" not found`
                };
            }
            
            const pools = this.poolsConfig[providerName];
            let targetPool = null;
            
            for (const pool of pools) {
                if (customName) {
                    if (pool.customName === customName || pool.uuid === customName) {
                        targetPool = pool;
                        break;
                    }
                }
            }
            
            if (!targetPool) {
                return {
                    success: false,
                    error: `Provider instance "${customName}" not found`
                };
            }
            
            targetPool.needsRefresh = true;
            targetPool.lastRefreshTime = new Date().toISOString();
            
            await this.savePoolsConfig();
            
            logger.info(`[Model Switch Service] Refreshed provider: ${customName}`);
            
            return {
                success: true,
                data: {
                    providerName,
                    customName,
                    timestamp: new Date().toISOString()
                }
            };
        } catch (error) {
            logger.error('[Model Switch Service] Failed to refresh provider:', error.message);
            return {
                success: false,
                error: error.message
            };
        }
    }
}

const modelSwitchService = new ModelSwitchService();

export { ModelSwitchService, modelSwitchService };
export default modelSwitchService;
