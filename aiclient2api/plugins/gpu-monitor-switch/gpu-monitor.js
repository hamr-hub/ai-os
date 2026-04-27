import logger from '../../utils/logger.js';
import { backendClient, GO_BACKEND_URL, PYTHON_BACKEND_URL } from './backend-client.js';

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
        logger.info('[GPU Monitor Service] Initializing GPU monitor (with Go/Python fallback)...');
        this.startMonitoring();
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

            if (result.status === 'unavailable' || !result.current) {
                this.gpuData = [];
                return;
            }

            const gpu = result.current;
            const gpuItem = {
                index: 0,
                name: gpu.name || 'Unknown GPU',
                temperature: gpu.temperature ?? null,
                gpuUtilization: gpu.gpu_utilization ?? gpu.utilization?.percent ?? gpu.utilization ?? null,
                memoryUsed: gpu.memory_used ?? gpu.used_memory ?? null,
                memoryTotal: gpu.memory_total ?? gpu.total_memory ?? null,
                memoryFree: gpu.memory_free ?? gpu.available_memory ?? null,
                memoryUsagePercent: gpu.memory_usage_percent ?? gpu.memory_utilization?.percent ?? null,
                memoryUtilization: gpu.memory_utilization?.percent ?? null,
                powerDraw: gpu.power_draw ?? null,
                powerLimit: gpu.power_limit ?? null,
                powerPercent: gpu.power_percent ?? null,
                fanSpeed: gpu.fan_speed ?? null,
                gpuCount: 1,
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
            return { success: true, data: this.gpuData, timestamp: new Date().toISOString() };
        } catch (error) {
            return { success: false, error: error.message, timestamp: new Date().toISOString() };
        }
    }

    getLatestGPUData() {
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
        logger.info(`[GPU Monitor Service] Updated monitoring interval to ${newInterval}ms`);
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
