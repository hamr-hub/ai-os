import logger from '../../utils/logger.js';
import { backendClient } from './backend-client.js';

class HealthMonitorService {
    constructor() {
        this.alertCache = null;
        this.detailCache = null;
        this.historyCache = [];
        this.lastFetchTime = null;
        this.pollingInterval = null;
        this.isPolling = false;
        this.refreshInterval = 10000;
        this.maxHistoryLength = 100;
    }

    async init() {
        logger.info('[HealthMonitor] Initializing...');
        this.startPolling();
    }

    async destroy() {
        this.stopPolling();
        logger.info('[HealthMonitor] Destroyed');
    }

    startPolling() {
        if (this.isPolling) return;
        this.isPolling = true;
        this.updateData();
        this.pollingInterval = setInterval(() => this.updateData(), this.refreshInterval);
    }

    stopPolling() {
        if (!this.isPolling) return;
        this.isPolling = false;
        if (this.pollingInterval) { clearInterval(this.pollingInterval); this.pollingInterval = null; }
    }

    async updateData() {
        try {
            await Promise.allSettled([
                this.fetchAlert(),
                this.fetchDetail(),
            ]);
            this.lastFetchTime = new Date().toISOString();
        } catch (error) {
            logger.error('[HealthMonitor] Update error:', error.message);
        }
    }

    async fetchAlert() {
        try {
            const response = await backendClient.fetchWithFallback('/manage/health/alert');
            if (!response.ok) return;
            const result = await response.json();
            this.alertCache = result;
            this._addToHistory(result);
        } catch (error) {
            logger.error('[HealthMonitor] Alert fetch error:', error.message);
        }
    }

    async fetchDetail() {
        try {
            const response = await backendClient.fetchWithFallback('/manage/health/detailed');
            if (!response.ok) return;
            this.detailCache = await response.json();
        } catch (error) {
            logger.error('[HealthMonitor] Detail fetch error:', error.message);
        }
    }

    _addToHistory(alertResult) {
        const entry = {
            timestamp: new Date().toISOString(),
            health_score: alertResult.health_score || 0,
            status: alertResult.status || 'unknown',
            alert_count: (alertResult.alert_reasons || []).length,
        };
        this.historyCache.push(entry);
        if (this.historyCache.length > this.maxHistoryLength) {
            this.historyCache = this.historyCache.slice(-this.maxHistoryLength);
        }
    }

    getAlert() {
        return { success: true, data: this.alertCache, timestamp: new Date().toISOString(), backendStatus: backendClient.getStatus() };
    }

    getDetail() {
        return { success: true, data: this.detailCache, timestamp: new Date().toISOString(), backendStatus: backendClient.getStatus() };
    }

    getHistory() {
        return { success: true, data: this.historyCache, count: this.historyCache.length };
    }

    async runCheck() {
        try {
            const response = await backendClient.fetchWithFallback('/manage/health/check', { method: 'POST' });
            const result = await response.json();
            await this.fetchAlert();
            await this.fetchDetail();
            return { success: response.ok, data: result };
        } catch (error) {
            logger.error('[HealthMonitor] Check error:', error.message);
            return { success: false, error: error.message };
        }
    }
}

const healthMonitor = new HealthMonitorService();
export { HealthMonitorService, healthMonitor };
export default healthMonitor;
