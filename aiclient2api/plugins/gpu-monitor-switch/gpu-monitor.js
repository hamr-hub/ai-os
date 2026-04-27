import { exec } from 'child_process';
import { promisify } from 'util';
import logger from '../../utils/logger.js';

const execAsync = promisify(exec);

class GPUMonitorService {
    constructor() {
        this.gpuData = [];
        this.monitoringInterval = null;
        this.isMonitoring = false;
        this.refreshInterval = 5000;
    }

    async init() {
        logger.info('[GPU Monitor Service] Initializing GPU monitor...');
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
        
        this.monitoringInterval = setInterval(() => {
            this.updateGPUData();
        }, this.refreshInterval);
        
        logger.info(`[GPU Monitor Service] Started monitoring (interval: ${this.refreshInterval}ms)`);
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
            this.gpuData = await this.getGPUInfo();
        } catch (error) {
            logger.error('[GPU Monitor Service] Failed to get GPU info:', error.message);
        }
    }

    async getGPUInfo() {
        try {
            const { stdout } = await execAsync(
                'nvidia-smi --query-gpu=index,name,temperature.gpu,utilization.gpu,memory.used,memory.total,memory.free,utilization.memory,power.draw,power.limit --format=csv,noheader,nounits'
            );
            
            const lines = stdout.trim().split('\n').filter(line => line.trim());
            
            return lines.map((line, idx) => {
                const parts = line.split(',').map(part => part.trim());
                
                if (parts.length < 10) {
                    logger.warn('[GPU Monitor Service] Invalid nvidia-smi output format');
                    return null;
                }
                
                const gpuIndex = parseInt(parts[0]);
                const gpuName = parts[1];
                const temperature = parts[2] !== '[N/A]' ? parseFloat(parts[2]) : null;
                const gpuUtilization = parts[3] !== '[N/A]' ? parseFloat(parts[3]) : null;
                const memoryUsed = parts[4] !== '[N/A]' ? parseFloat(parts[4]) : null;
                const memoryTotal = parts[5] !== '[N/A]' ? parseFloat(parts[5]) : null;
                const memoryFree = parts[6] !== '[N/A]' ? parseFloat(parts[6]) : null;
                const memoryUtilization = parts[7] !== '[N/A]' ? parseFloat(parts[7]) : null;
                const powerDraw = parts[8] !== '[N/A]' ? parseFloat(parts[8]) : null;
                const powerLimit = parts[9] !== '[N/A]' ? parseFloat(parts[9]) : null;
                
                const memoryUsagePercent = memoryTotal > 0 ? ((memoryUsed / memoryTotal) * 100).toFixed(1) : null;
                
                return {
                    index: gpuIndex,
                    name: gpuName,
                    temperature,
                    gpuUtilization,
                    memoryUsed,
                    memoryTotal,
                    memoryFree,
                    memoryUsagePercent,
                    memoryUtilization,
                    powerDraw,
                    powerLimit,
                    timestamp: new Date().toISOString()
                };
            }).filter(gpu => gpu !== null);
        } catch (error) {
            logger.error('[GPU Monitor Service] Error getting GPU info:', error.message);
            
            if (error.message.includes('nvidia-smi')) {
                logger.warn('[GPU Monitor Service] nvidia-smi not available, returning mock data');
                return this.getMockGPUData();
            }
            
            return [];
        }
    }

    getMockGPUData() {
        return [
            {
                index: 0,
                name: 'NVIDIA GeForce RTX 4090',
                temperature: 65,
                gpuUtilization: 75.5,
                memoryUsed: 16384,
                memoryTotal: 24576,
                memoryFree: 8192,
                memoryUsagePercent: 66.7,
                memoryUtilization: 45.2,
                powerDraw: 280.5,
                powerLimit: 450.0,
                timestamp: new Date().toISOString()
            },
            {
                index: 1,
                name: 'NVIDIA GeForce RTX 4090',
                temperature: 62,
                gpuUtilization: 82.3,
                memoryUsed: 18432,
                memoryTotal: 24576,
                memoryFree: 6144,
                memoryUsagePercent: 75.0,
                memoryUtilization: 52.1,
                powerDraw: 310.2,
                powerLimit: 450.0,
                timestamp: new Date().toISOString()
            }
        ];
    }

    async getGPUInfoSync() {
        try {
            const gpuData = await this.getGPUInfo();
            return {
                success: true,
                data: gpuData,
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            logger.error('[GPU Monitor Service] Error in getGPUInfoSync:', error.message);
            return {
                success: false,
                error: error.message,
                timestamp: new Date().toISOString()
            };
        }
    }

    getLatestGPUData() {
        return {
            success: true,
            data: this.gpuData,
            timestamp: new Date().toISOString(),
            isMonitoring: this.isMonitoring
        };
    }

    setMonitoringInterval(interval) {
        const newInterval = parseInt(interval);
        if (isNaN(newInterval) || newInterval < 1000) {
            return { success: false, error: 'Interval must be at least 1000ms' };
        }
        
        this.refreshInterval = newInterval;
        
        if (this.isMonitoring) {
            this.stopMonitoring();
            this.startMonitoring();
        }
        
        logger.info(`[GPU Monitor Service] Updated monitoring interval to ${newInterval}ms`);
        return { success: true, interval: newInterval };
    }

    getMonitoringStatus() {
        return {
            success: true,
            isMonitoring: this.isMonitoring,
            interval: this.refreshInterval,
            gpuCount: this.gpuData.length
        };
    }
}

const gpuMonitorService = new GPUMonitorService();

export { GPUMonitorService, gpuMonitorService };
export default gpuMonitorService;
