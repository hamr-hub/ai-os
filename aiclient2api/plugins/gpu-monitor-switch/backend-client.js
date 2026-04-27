import logger from '../../utils/logger.js';

const GO_BACKEND_URL = process.env.GO_BACKEND_URL || 'http://localhost:35001';
const PYTHON_BACKEND_URL = process.env.PYTHON_BACKEND_URL || 'http://localhost:35000';

class BackendClient {
    constructor() {
        this.activeBackend = 'go';
        this.goAvailable = true;
        this.pythonAvailable = true;
        this.lastGoCheck = 0;
        this.lastPythonCheck = 0;
        this.healthCheckInterval = 30000;
        this._startHealthChecks();
    }

    _startHealthChecks() {
        this._checkGoHealth();
        this._checkPythonHealth();
        setInterval(() => {
            this._checkGoHealth();
            this._checkPythonHealth();
        }, this.healthCheckInterval);
    }

    async _checkGoHealth() {
        try {
            const response = await fetch(`${GO_BACKEND_URL}/health`, { signal: AbortSignal.timeout(5000) });
            this.goAvailable = response.ok;
            this.lastGoCheck = Date.now();
            if (this.goAvailable && this.activeBackend === 'python') {
                logger.info('[BackendClient] Go backend recovered, switching back');
                this.activeBackend = 'go';
            }
        } catch {
            this.goAvailable = false;
            this.lastGoCheck = Date.now();
            if (this.activeBackend === 'go') {
                logger.warn('[BackendClient] Go backend unavailable, falling back to Python');
                this.activeBackend = 'python';
            }
        }
    }

    async _checkPythonHealth() {
        try {
            const response = await fetch(`${PYTHON_BACKEND_URL}/health`, { signal: AbortSignal.timeout(5000) });
            this.pythonAvailable = response.ok;
            this.lastPythonCheck = Date.now();
        } catch {
            this.pythonAvailable = false;
            this.lastPythonCheck = Date.now();
        }
    }

    getBaseUrl() {
        if (this.activeBackend === 'python') {
            return PYTHON_BACKEND_URL;
        }
        return GO_BACKEND_URL;
    }

    getManagePrefix() {
        if (this.activeBackend === 'python') {
            return '/manage';
        }
        return '/manage';
    }

    getV1Prefix() {
        return '/v1';
    }

    getApiPrefix() {
        if (this.activeBackend === 'python') {
            return '/manage';
        }
        return '/api';
    }

    async fetchWithFallback(path, options = {}) {
        const goUrl = `${GO_BACKEND_URL}${path}`;
        const pythonUrl = `${PYTHON_BACKEND_URL}${path}`;

        if (this.activeBackend === 'go' && this.goAvailable) {
            try {
                const response = await fetch(goUrl, { ...options, signal: options.signal || AbortSignal.timeout(10000) });
                if (response.ok) return response;
                logger.warn('[BackendClient] Go backend returned error, trying Python fallback');
            } catch (error) {
                logger.warn('[BackendClient] Go backend request failed:', error.message);
                if (!this.pythonAvailable) {
                    throw error;
                }
            }
        }

        this.activeBackend = 'python';
        try {
            const response = await fetch(pythonUrl, { ...options, signal: options.signal || AbortSignal.timeout(10000) });
            if (response.ok) return response;
            throw new Error(`Python backend returned ${response.status}`);
        } catch (error) {
            logger.error('[BackendClient] Both backends failed for path:', path);
            throw error;
        }
    }

    async postWithFallback(path, body) {
        return this.fetchWithFallback(path, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
    }

    getStatus() {
        return {
            activeBackend: this.activeBackend,
            goAvailable: this.goAvailable,
            pythonAvailable: this.pythonAvailable,
            goUrl: GO_BACKEND_URL,
            pythonUrl: PYTHON_BACKEND_URL,
        };
    }
}

const backendClient = new BackendClient();
export { BackendClient, backendClient, GO_BACKEND_URL, PYTHON_BACKEND_URL };
export default backendClient;
