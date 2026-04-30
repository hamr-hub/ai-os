import logger from '../../utils/logger.js';

const GO_BACKEND_URL = process.env.GO_BACKEND_URL || 'http://localhost:35001';
const PYTHON_BACKEND_URL = process.env.PYTHON_BACKEND_URL || 'http://localhost:35000';

class BackendClient {
    constructor() {
        this.activeBackend = 'go';
        this.goAvailable = false;
        this.pythonAvailable = true;
        this.lastGoCheck = 0;
        this.lastPythonCheck = 0;
        this.healthCheckInterval = 30000;
        this._consecutiveGoFailures = 0;
        this._consecutivePythonFailures = 0;
        this._failThreshold = 3;
        this._goCoolingUntil = 0;
        this._pythonCoolingUntil = 0;
        this._coolingDuration = 60000;
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
            const response = await fetch(`${GO_BACKEND_URL}/manage/gpu/summary`, { signal: AbortSignal.timeout(5000) });
            if (response.ok) {
                this.goAvailable = true;
                this._consecutiveGoFailures = 0;
                this._goCoolingUntil = 0;
            } else {
                this._consecutiveGoFailures++;
                this.goAvailable = this._consecutiveGoFailures < this._failThreshold;
            }
            this.lastGoCheck = Date.now();
            if (!this.goAvailable && this.activeBackend === 'go') {
                logger.warn('[BackendClient] Go backend unavailable after %d consecutive failures, falling back to Python', this._consecutiveGoFailures);
                this.activeBackend = 'python';
                this._goCoolingUntil = Date.now() + this._coolingDuration;
            } else if (this.goAvailable && this.activeBackend !== 'go' && Date.now() > this._goCoolingUntil) {
                logger.info('[BackendClient] Go backend recovered, switching to Go');
                this.activeBackend = 'go';
            }
        } catch (e) {
            this._consecutiveGoFailures++;
            this.goAvailable = false;
            this.lastGoCheck = Date.now();
            if (this.activeBackend === 'go') {
                logger.warn('[BackendClient] Go backend unreachable (failure %d), falling back to Python', this._consecutiveGoFailures);
                this.activeBackend = 'python';
                this._goCoolingUntil = Date.now() + this._coolingDuration;
            }
        }
    }/manage/gpu/summary`, { signal: AbortSignal.timeout(5000) });
            if (response.ok) {
                this.goAvailable = true;
            } else {
                this.goAvailable = false;
            }
            this.lastGoCheck = Date.now();
            if (!this.goAvailable && this.activeBackend === 'go') {
                logger.warn('[BackendClient] Go backend GPU unavailable, falling back to Python');
                this.activeBackend = 'python';
            } else if (this.goAvailable && this.activeBackend !== 'go') {
                logger.info('[BackendClient] Go backend available, switching to Go');
                this.activeBackend = 'go';
            }
        } catch (e) {
            this.goAvailable = false;
            this.lastGoCheck = Date.now();
            if (this.activeBackend === 'go') {
                logger.warn('[BackendClient] Go backend unreachable, falling back to Python');
                this.activeBackend = 'python';
            }
        }
    }

    async _checkPythonHealth() {
        try {
            const response = await fetch(`${PYTHON_BACKEND_URL}/manage/gpu/summary`, { signal: AbortSignal.timeout(5000) });
            if (response.ok) {
                this.pythonAvailable = true;
                this._consecutivePythonFailures = 0;
                this._pythonCoolingUntil = 0;
            } else {
                this._consecutivePythonFailures++;
                this.pythonAvailable = this._consecutivePythonFailures < this._failThreshold;
            }
            this.lastPythonCheck = Date.now();
        } catch (e) {
            this._consecutivePythonFailures++;
            this.pythonAvailable = false;
            this.lastPythonCheck = Date.now();
            if (this.activeBackend === 'python') {
                logger.warn('[BackendClient] Python backend unreachable (failure %d)', this._consecutivePythonFailures);
            }
        }
    }/manage/gpu/summary`, { signal: AbortSignal.timeout(5000) });
            this.pythonAvailable = response.ok;
            this.lastPythonCheck = Date.now();
        } catch (e) {
            this.pythonAvailable = false;
            this.lastPythonCheck = Date.now();
            if (this.activeBackend === 'python') {
                logger.warn('[BackendClient] Python backend unreachable');
            }
        }
    }

    getBaseUrl() {
        if (this.activeBackend === 'go' && this.goAvailable) {
            return GO_BACKEND_URL;
        }
        return PYTHON_BACKEND_URL;
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
        const isAtomicSwitch = path.includes('/switch/atomic');
        const isSwitchStatus = path.includes('/switch/status');
        const isSwitchCancel = path.includes('/switch/cancel');
        const isModelSwitch = isAtomicSwitch || isSwitchStatus || isSwitchCancel;
        const isModelStart = path.includes('/start');
        const isModelStop = path.includes('/stop');
        const isLongOperation = isModelSwitch || isModelStart || isModelStop;

        const defaultTimeout = isLongOperation ? 180000 : (options.method === 'POST' ? 60000 : 10000);
        const timeoutSignal = options.signal || AbortSignal.timeout(defaultTimeout);

        const goUrl = `${GO_BACKEND_URL}${path}`;
        const pythonUrl = `${PYTHON_BACKEND_URL}${path}`;

        if (isModelSwitch) {
            if (this.goAvailable) {
                try {
                    logger.info('[BackendClient] Model switch -> Go backend');
                    const response = await fetch(goUrl, { ...options, signal: timeoutSignal });
                    if (response.ok) return response;
                    logger.warn(`[BackendClient] Go backend returned ${response.status} for model switch, trying Python fallback`);
                } catch (error) {
                    logger.warn('[BackendClient] Go backend failed for model switch, trying Python fallback:', error.message);
                }
            }
            if (this.pythonAvailable) {
                try {
                    this.activeBackend = 'python';
                    logger.info('[BackendClient] Model switch -> Python backend fallback');
                    const pythonTimeoutSignal = options.signal || AbortSignal.timeout(180000);
                    const response = await fetch(pythonUrl, { ...options, signal: pythonTimeoutSignal });
                    if (response.ok) return response;
                    logger.warn(`[BackendClient] Python backend returned ${response.status} for model switch`);
                    return response;
                } catch (error) {
                    logger.error('[BackendClient] Python backend failed for model switch:', error.message);
                    throw new Error(`Python backend failed for model switch: ${error.message}`);
                }
            }
            throw new Error('No available backend for model switch');
        }

        if (isLongOperation) {
            if (this.goAvailable) {
                try {
                    logger.info(`[BackendClient] Long operation (${isModelStart ? 'start' : 'stop'}) -> Go backend`);
                    const response = await fetch(goUrl, { ...options, signal: timeoutSignal });
                    if (response.ok) return response;
                    logger.warn('[BackendClient] Go backend returned error for long operation, trying Python');
                } catch (error) {
                    logger.warn('[BackendClient] Go backend failed for long operation:', error.message);
                }
            }
            if (this.pythonAvailable) {
                try {
                    logger.info(`[BackendClient] Long operation (${isModelStart ? 'start' : 'stop'}) -> Python backend`);
                    const pythonTimeoutSignal = options.signal || AbortSignal.timeout(180000);
                    const response = await fetch(pythonUrl, { ...options, signal: pythonTimeoutSignal });
                    if (response.ok) return response;
                    logger.warn('[BackendClient] Python backend returned error for long operation');
                } catch (error) {
                    logger.warn('[BackendClient] Python backend failed for long operation:', error.message);
                }
            }
            throw new Error(`Both backends failed for long operation: ${path}`);
        }

        if (this.activeBackend === 'go' && this.goAvailable) {
            try {
                const response = await fetch(goUrl, { ...options, signal: timeoutSignal });
                if (response.ok) return response;
                logger.warn('[BackendClient] Go backend returned error, trying Python fallback');
            } catch (error) {
                logger.warn('[BackendClient] Go backend request failed:', error.message);
                if (!this.pythonAvailable) {
                    throw error;
                }
            }
        }

        if (this.pythonAvailable) {
            try {
                const response = await fetch(pythonUrl, { ...options, signal: timeoutSignal });
                if (response.ok) {
                    if (this.activeBackend === 'go') this._consecutiveGoFailures++;
                    return response;
                }
            } catch (error) {
                logger.warn('[BackendClient] Python backend request failed:', error.message);
            }
        }

        if (this.goAvailable) {
            try {
                const response = await fetch(goUrl, { ...options, signal: timeoutSignal });
                if (response.ok) return response;
            } catch (error) {
                logger.warn('[BackendClient] Go backend fallback failed:', error.message);
            }
        }

        throw new Error(`Both backends failed for path: ${path}`);
    }

    async postWithFallback(path, body, options = {}) {
        return this.fetchWithFallback(path, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
            ...options
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
