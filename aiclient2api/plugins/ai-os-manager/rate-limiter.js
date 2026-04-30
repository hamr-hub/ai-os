import logger from '../../utils/logger.js';
import { backendClient } from './backend-client.js';

class RateLimiterService {
    constructor() {
        this.queueCache = null;
        this.configCache = null;
        this.statsCache = null;
        this.lastFetchTime = null;
        this.pollingInterval = null;
        this.isPolling = false;
        this.refreshInterval = 5000;
    }

    async init() {
        logger.info('[RateLimiter] Initialized (polling deferred, starts on first data request)');
    }

    async destroy() {
        this.stopPolling();
        logger.info('[RateLimiter] Destroyed');
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
                this.fetchQueue(),
                this.fetchStats(),
            ]);
            this.lastFetchTime = new Date().toISOString();
        } catch (error) {
            logger.error('[RateLimiter] Update error:', error.message);
        }
    }

    async fetchQueue() {
        try {
            const response = await backendClient.fetchWithFallback('/manage/queue');
            if (!response.ok) return;
            this.queueCache = await response.json();
        } catch (error) {
            logger.error('[RateLimiter] Queue fetch error:', error.message);
        }
    }

    async fetchConfig() {
        try {
            const response = await backendClient.fetchWithFallback('/manage/ratelimit/config');
            if (!response.ok) return;
            this.configCache = await response.json();
        } catch (error) {
            logger.error('[RateLimiter] Config fetch error:', error.message);
            this.configCache = {
                ip_qps_limit: 100,
                ip_qps_window_seconds: 60,
                concurrency_limit: 32,
                queue_timeout_seconds: 30,
                whitelist_ips: ['127.0.0.1', 'localhost'],
                rate_limited_paths: ['/v1/chat/completions', '/v1/completions', '/v1/embeddings', '/v1/images/generations'],
            };
        }
    }

    async fetchStats() {
        try {
            const response = await backendClient.fetchWithFallback('/manage/ratelimit/stats');
            if (!response.ok) return;
            this.statsCache = await response.json();
        } catch (error) {
            logger.error('[RateLimiter] Stats fetch error:', error.message);
            this.statsCache = {
                total_rejected: 0,
                recent_429_count: 0,
                rejection_by_ip: {},
                rejection_by_path: {},
                current_queue_depth: 0,
                timestamp: new Date().toISOString(),
            };
        }
    }

    getQueueStatus() {
        if (!this.isPolling) this.startPolling();
        return { success: true, data: this.queueCache, timestamp: new Date().toISOString(), backendStatus: backendClient.getStatus() };
    }

    getConfig() {
        return { success: true, data: this.configCache, timestamp: new Date().toISOString() };
    }

    getStats() {
        return { success: true, data: this.statsCache, timestamp: new Date().toISOString() };
    }

    async updateConfig(newConfig) {
        try {
            const response = await backendClient.fetchWithFallback('/manage/ratelimit/config', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(newConfig)
            });
            const result = await response.json();
            this.configCache = result;
            return { success: response.ok, data: result };
        } catch (error) {
            return { success: false, error: error.message };
        }
    }
}

const rateLimiter = new RateLimiterService();
export { RateLimiterService, rateLimiter };
export default rateLimiter;
