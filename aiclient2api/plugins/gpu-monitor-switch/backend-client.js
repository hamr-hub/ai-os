import logger from '../../utils/logger.js';

const GO_BACKEND_URL = process.env.GO_BACKEND_URL || 'http://192.168.7.103:35001';
const PYTHON_BACKEND_URL = process.env.PYTHON_BACKEND_URL || 'http://192.168.7.103:35000';

class BackendClient {
    constructor() {
        this.activeBackend = 'python';
        this.goAvailable = false;
        this.pythonAvailable = true;
        this.lastGoCheck = 0;
        this.lastPythonCheck = 0;
        this.healthCheckInterval = 30000;
        this._startHealthChecks();
    }

    _startHealthChecks() {
        this._checkPythonHealth();
        this._checkGoHealth();
        setInterval(() => {
            this._checkPythonHealth();
            this._checkGoHealth();
        }, this.healthCheckInterval);
    }

    async _checkGoHealth() {
        try {
            const response = await fetch(`${GO_BACKEND_URL}/manage/gpu/summary`, { signal: AbortSignal.timeout(5000) });
            if (response.ok) {
                const data = await response.json();
                this.goAvailable = data.status === 'available' && data.current != null;
            } else {
                this.goAvailable = false;
            }
            this.lastGoCheck = Date.now();
            if (this.goAvailable && this.activeBackend !== 'go') {
                logger.info('[BackendClient] Go backend GPU available, switching to Go');
                this.activeBackend = 'go';
            }
        } catch (e) {
            this.goAvailable = false;
            this.lastGoCheck = Date.now();
            if (this.activeBackend === 'go') {
                logger.warn('[BackendClient] Go backend GPU unavailable, falling back to Python');
                this.activeBackend = 'python';
            }
        }
    }

    async _checkPythonHealth() {
        try {
            const response = await fetch(`${PYTHON_BACKEND_URL}/health`, { signal: AbortSignal.timeout(5000) });
            this.pythonAvailable = response.ok;
            this.lastPythonCheck = Date.now();
        } catch (e) {
            this.pythonAvailable = false;
            this.lastPythonCheck = Date.now();
            if (this.activeBackend === 'python') {
                logger.warn('[BackendClient] Python backend unavailable');
            }
        }
    }

    getBaseUrl() {
        if (this.activeBackend === 'python') {
            return PYTHON_BACKEND_URL;
        }
        return GO_BACKEND_URL;
    }

    getManagePrefix() {
        return '/manage';
    }

    getV1Prefix() {
        return '/v1';
    }

    getApiPrefix() {
        return '/manage';
    }

    async fetchWithFallback(path, options = {}) {
        const pythonUrl = `${PYTHON_BACKEND_URL}${path}`;
        const goUrl = `${GO_BACKEND_URL}${path}`;

        if (this.activeBackend === 'python' && this.pythonAvailable) {
            try {
                const response = await fetch(pythonUrl, { ...options, signal: options.signal || AbortSignal.timeout(10000) });
                if (response.ok) return response;
                logger.warn('[BackendClient] Python backend returned error, trying Go fallback');
            } catch (error) {
                logger.warn('[BackendClient] Python backend request failed:', error.message);
                if (!this.goAvailable) {
                    throw error;
                }
            }
        }

        if (this.goAvailable) {
            this.activeBackend = 'go';
            try {
                const response = await fetch(goUrl, { ...options, signal: options.signal || AbortSignal.timeout(10000) });
                if (response.ok) return response;
            } catch (error) {
                logger.warn('[BackendClient] Go backend request failed:', error.message);
            }
        }

        throw new Error(`Both backends failed for path: ${path}`);
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
