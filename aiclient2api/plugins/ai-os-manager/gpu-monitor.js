import logger from '../../utils/logger.js';
import { backendClient, GO_BACKEND_URL, PYTHON_BACKEND_URL } from './backend-client.js';
import { normalizeBackendResult } from './api-handler.js';

class GPUMonitorService {
    constructor() {
        this.gpuData = [];
        this.gpuHistory = [];
        this.monitoringInterval = null;
        this.isMonitoring = false;
        this.refreshInterval = 5000;
        this.maxHistory = 60;
    }

    async init() {
        logger.info('[GPU Monitor Service] Initialized (monitoring deferred, starts on first data request)');
    }

    async destroy() {
        this.stopMonitoring();
        logger.info('[GPU Monitor Service] GPU monitor stopped');
    }

    startMonitoring() {
        if (this.isMonitoring) return;
        this.isMonitoring = true;
        this.updateGPUData();
        this.monitoringInterval = setInterval(() => { this.updateGPUData(); }, this.refreshInterval);
        logger.info(`[GPU Monitor Service] Started monitoring (interval: ${this.refreshInterval}ms, backend: ${backendClient.activeBackend})`);
    }

    stopMonitoring() {
        if (!this.isMonitoring) return;
        this.isMonitoring = false;
        if (this.monitoringInterval) {
            clearInterval(this.monitoringInterval);
            this.monitoringInterval = null;
        }
        logger.info('[GPU Monitor Service] Stopped monitoring');
    }

    async updateGPUData() {
        try {
            const response = await backendClient.fetchWithFallback('/manage/gpu/summary');
            if (!response.ok) return;
            const result = await response.json();

            if (result.status === 'unavailable') {
                this.gpuData = [];
                return;
            }

            const g = normalizeBackendResult(result);
            if (!g || !g.name) {
                this.gpuData = [];
                return;
            }

            const gpuUtil = typeof g.utilization === 'number' ? g.utilization : (g.utilization?.percent ?? g.utilization ?? null);
            const memUtil = typeof g.memory_utilization === 'number' ? g.memory_utilization : (g.memory_utilization?.percent ?? null);
            const memUsed = typeof g.used_memory === 'number' ? g.used_memory : (g.memory_used ?? null);
            const memTotal = typeof g.total_memory === 'number' ? g.total_memory : (g.memory_total ?? null);
            const memFree = typeof g.available_memory === 'number' ? g.available_memory : (g.memory_free ?? null);

            const gpuItem = {
                index: g.index ?? 0,
                name: g.name || 'Unknown GPU',
                temperature: g.temperature ?? null,
                gpuUtilization: gpuUtil,
                memoryUsed: memUsed,
                memoryTotal: memTotal,
                memoryFree: memFree,
                memoryUsagePercent: memUtil,
                memoryUtilization: memUtil,
                powerDraw: g.power_draw ?? null,
                powerLimit: g.power_limit ?? null,
                powerPercent: g.power_percent ?? null,
                fanSpeed: g.fan_speed ?? null,
                processes: g.processes || result.processes || [],
                gpuCount: result.gpu_count || 1,
                timestamp: new Date().toISOString()
            };

            this.gpuData = [gpuItem];
            this.gpuHistory.push({
                timestamp: gpuItem.timestamp,
                utilization: gpuItem.gpuUtilization,
                memory: gpuItem.memoryUsagePercent,
                temperature: gpuItem.temperature
            });

            if (this.gpuHistory.length > this.maxHistory) {
                this.gpuHistory.shift();
            }
        } catch (error) {
            logger.error('[GPU Monitor Service] Error fetching GPU data:', error.message);
        }
    }

    async getGPUInfoSync() {
        try {
            await this.updateGPUData();
            return { success: true, data: this.gpuData, history: this.gpuHistory, timestamp: new Date().toISOString() };
        } catch (error) {
            return { success: false, error: error.message, timestamp: new Date().toISOString() };
        }
    }

    getLatestGPUData() {
        if (!this.isMonitoring) this.startMonitoring();
        return {
            success: true,
            data: this.gpuData,
            history: this.gpuHistory,
            timestamp: new Date().toISOString(),
            isMonitoring: this.isMonitoring,
            backendStatus: backendClient.getStatus()
        };
    }

    setMonitoringInterval(interval) {
        const newInterval = parseInt(interval);
        if (isNaN(newInterval) || newInterval < 1000) return { success: false, error: 'Interval must be at least 1000ms' };
        this.refreshInterval = newInterval;
        if (this.isMonitoring) { this.stopMonitoring(); this.startMonitoring(); }
        logger.info(`[GPU Monitor Service] Updated interval to ${newInterval}ms`);
        return { success: true, interval: newInterval };
    }

    getMonitoringStatus() {
        return {
            success: true,
            isMonitoring: this.isMonitoring,
            interval: this.refreshInterval,
            gpuCount: this.gpuData.length,
            historyLength: this.gpuHistory.length,
            backendStatus: backendClient.getStatus()
        };
    }
}

const gpuMonitorService = new GPUMonitorService();

export { GPUMonitorService, gpuMonitorService };
export default gpuMonitorService;
