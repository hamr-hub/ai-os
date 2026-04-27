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

    normalizeNumber(value) {
        if (value === null || value === undefined || value === '') return null;
        const num = Number(value);
        return Number.isFinite(num) ? num : null;
    }

    normalizePercentage(value) {
        const num = this.normalizeNumber(value);
        if (num === null) return null;
        if (num <= 1) return num * 100;
        return num;
    }

    normalizeMemoryValue(value) {
        const num = this.normalizeNumber(value);
        if (num === null) return null;
        if (num > 1024 * 1024 * 16) return num;
        return num * 1024 * 1024;
    }

    buildGPUItem(source, index = 0, fallbackProcesses = []) {
        const totalMemory = this.normalizeMemoryValue(source.memory_total ?? source.total_memory);
        const usedMemory = this.normalizeMemoryValue(source.memory_used ?? source.used_memory);
        const freeMemory = this.normalizeMemoryValue(source.memory_free ?? source.available_memory ?? source.free_memory);
        const memoryUsagePercent = this.normalizePercentage(
            source.memory_usage_percent
            ?? source.memory_utilization?.percent
            ?? source.memory_utilization
            ?? (usedMemory !== null && totalMemory ? (usedMemory / totalMemory) * 100 : null)
        );

        return {
            index,
            name: source.name || `GPU ${index}`,
            temperature: this.normalizeNumber(source.temperature),
            gpuUtilization: this.normalizePercentage(source.gpu_utilization ?? source.utilization?.percent ?? source.utilization),
            memoryUsed: usedMemory,
            memoryTotal: totalMemory,
            memoryFree: freeMemory,
            memoryUsagePercent,
            memoryUtilization: memoryUsagePercent,
            powerDraw: this.normalizeNumber(source.power_draw),
            powerLimit: this.normalizeNumber(source.power_limit),
            powerPercent: this.normalizePercentage(source.power_percent),
            fanSpeed: this.normalizeNumber(source.fan_speed),
            processes: source.processes || fallbackProcesses || [],
            gpuCount: this.normalizeNumber(source.gpu_count) ?? 1,
            timestamp: new Date().toISOString()
        };
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

            const current = Array.isArray(result.current) ? result.current : [result.current || result.primary || result];
            const timestamp = new Date().toISOString();
            const nextGpuData = current
                .filter(Boolean)
                .map((gpu, index) => {
                    const item = this.buildGPUItem(gpu, index, result.processes || []);
                    item.timestamp = timestamp;
                    return item;
                });

            this.gpuData = nextGpuData;

            const primaryGpu = nextGpuData[0];
            if (primaryGpu) {
                this.gpuHistory.push({
                    timestamp,
                    utilization: primaryGpu.gpuUtilization,
                    memory: primaryGpu.memoryUsagePercent,
                    memoryUsed: primaryGpu.memoryUsed,
                    memoryTotal: primaryGpu.memoryTotal,
                    temperature: primaryGpu.temperature
                });
            }

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
