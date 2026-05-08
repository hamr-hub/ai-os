import { gpuMonitorService } from './gpu-monitor.js';
import { modelSwitchService } from './model-switch.js';
import { engineManager } from './engine-manager.js';
import { backendClient } from './backend-client.js';
import logger from '../../utils/logger.js';
import fs from 'fs/promises';
import pathModule from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = pathModule.dirname(__filename);
const pluginDir = __dirname;
const staticDir = pathModule.resolve(process.cwd(), 'static');

export function normalizeBackendResult(result) {
    const field = result.current || result.primary || result.all?.[0] || result.all_gpus?.[0] || result;
    return { ...field, timestamp: new Date().toISOString() };
}

function parseRequestBody(req) {
    return new Promise((resolve, reject) => {
        let body = '';
        req.on('data', chunk => { body += chunk.toString(); });
        req.on('end', () => {
            try { resolve(body ? JSON.parse(body) : {}); }
            catch (error) { reject(error); }
        });
        req.on('error', reject);
    });
}

function sendJSONResponse(res, statusCode, data) {
    res.writeHead(statusCode, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(data));
}

function sendHTMLResponse(res, html) {
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(html);
}

async function proxyToBackend(res, path, method = 'GET', body = null) {
    try {
        const options = { method };
        if (body) {
            options.headers = { 'Content-Type': 'application/json' };
            options.body = JSON.stringify(body);
        }
        const response = await backendClient.fetchWithFallback(path, options);
        const text = await response.text();
        let data;
        try { data = text ? JSON.parse(text) : null; } catch { data = text; }
        sendJSONResponse(res, response.status, data || { success: response.ok });
    } catch (error) {
        sendJSONResponse(res, 500, { success: false, error: error.message });
    }
    return true;
}

export async function handleGetPanelHTML(method, urlPath, req, res) {
    if (method !== 'GET' || urlPath !== '/__panel_html__') return false;
    try {
        const html = await fs.readFile(pathModule.join(staticDir, 'index.html'), 'utf8');
        res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
        res.end(html);
        return true;
    } catch (error) {
        res.writeHead(404); res.end('Not found'); return true;
    }
}

export async function handlePanelRoute(method, urlPath, req, res) {
    if (method !== 'GET' || urlPath !== '/gpu-admin') return false;
    try {
        const html = await fs.readFile(pathModule.join(pluginDir, 'panel.html'), 'utf8');
        sendHTMLResponse(res, html);
        return true;
    } catch (error) {
        sendJSONResponse(res, 500, { success: false, error: 'Failed' });
        return true;
    }
}

export async function handleInjectScript(method, urlPath, req, res) {
    if (method !== 'GET' || urlPath !== '/plugins/ai-os-manager/inject.js') return false;
    try {
        const script = await fs.readFile(pathModule.join(pluginDir, 'inject.js'), 'utf8');
        res.writeHead(200, { 'Content-Type': 'application/javascript', 'Access-Control-Allow-Origin': '*' });
        res.end(script);
        return true;
    } catch (error) {
        sendJSONResponse(res, 500, { success: false, error: 'Failed' });
        return true;
    }
}

export async function handlePluginStyles(method, urlPath, req, res) {
    if (method !== 'GET' || urlPath !== '/plugins/ai-os-manager/styles.css') return false;
    try {
        const css = await fs.readFile(pathModule.join(pluginDir, 'styles.css'), 'utf8');
        res.writeHead(200, { 'Content-Type': 'text/css', 'Access-Control-Allow-Origin': '*' });
        res.end(css);
        return true;
    } catch (error) {
        sendJSONResponse(res, 500, { success: false, error: 'Failed' });
        return true;
    }
}

export async function handleGPUMonitorApiRoutes(method, urlPath, req, res, config) {
    if (!urlPath.startsWith('/api/gpu-monitor')) return false;
    try {
        if (urlPath === '/api/gpu-monitor' && method === 'GET') {
            sendJSONResponse(res, 200, gpuMonitorService.getLatestGPUData());
            return true;
        }
        if (urlPath === '/api/gpu-monitor/info' && method === 'GET') {
            sendJSONResponse(res, 200, await gpuMonitorService.getGPUInfoSync());
            return true;
        }
        if (urlPath === '/api/gpu-monitor/status' && method === 'GET') {
            sendJSONResponse(res, 200, gpuMonitorService.getMonitoringStatus());
            return true;
        }
        if (urlPath === '/api/gpu-monitor/start' && method === 'POST') {
            gpuMonitorService.startMonitoring();
            sendJSONResponse(res, 200, { success: true, message: 'Auto-monitoring started' });
            return true;
        }
        if (urlPath === '/api/gpu-monitor/stop' && method === 'POST') {
            gpuMonitorService.stopMonitoring();
            sendJSONResponse(res, 200, { success: true, message: 'Auto-monitoring stopped' });
            return true;
        }
        return false;
    } catch (error) {
        logger.error('[GPU Monitor API]', error.message);
        sendJSONResponse(res, 500, { success: false, error: error.message });
        return true;
    }
}

export async function handleModelSwitchApiRoutes(method, urlPath, req, res, config) {
    if (!urlPath.startsWith('/api/model-switch')) return false;
    try {
        if (urlPath === '/api/model-switch/models' && method === 'GET') {
            sendJSONResponse(res, 200, await modelSwitchService.getModelsList());
            return true;
        }
        if (urlPath === '/api/model-switch/switch-status' && method === 'GET') {
            sendJSONResponse(res, 200, await modelSwitchService.getSwitchStatus());
            return true;
        }
        if (urlPath === '/api/model-switch/aggregated' && method === 'GET') {
            const refresh = urlPath.includes('refresh=true');
            sendJSONResponse(res, 200, await modelSwitchService.getAggregatedModels(refresh));
            return true;
        }
        if (urlPath === '/api/model-switch/switch' && method === 'POST') {
            const body = await parseRequestBody(req);
            if (!body.modelName) { sendJSONResponse(res, 400, { success: false, error: 'Missing modelName' }); return true; }
            const options = {};
            if (body.engineType) options.engineType = body.engineType;
            if (body.port) options.port = body.port;
            sendJSONResponse(res, 200, await modelSwitchService.switchModel(body.modelName, body.async !== false, options));
            return true;
        }
        if (urlPath === '/api/model-switch/task-status' && method === 'GET') {
            const taskId = new URL(urlPath, 'http://localhost').searchParams.get('taskId');
            if (!taskId) { sendJSONResponse(res, 400, { success: false, error: 'Missing taskId' }); return true; }
            sendJSONResponse(res, 200, modelSwitchService.getSwitchTaskStatus(taskId));
            return true;
        }
        if (urlPath === '/api/model-switch/cancel' && method === 'POST') {
            sendJSONResponse(res, 200, await modelSwitchService.cancelSwitch());
            return true;
        }
        if (urlPath === '/api/model-switch/start' && method === 'POST') {
            const body = await parseRequestBody(req);
            sendJSONResponse(res, 200, await modelSwitchService.startModel(body.modelName));
            return true;
        }
        if (urlPath === '/api/model-switch/stop' && method === 'POST') {
            const body = await parseRequestBody(req);
            sendJSONResponse(res, 200, await modelSwitchService.stopModel(body.modelName));
            return true;
        }
        if (urlPath === '/api/model-switch/download' && method === 'POST') {
            const body = await parseRequestBody(req);
            if (!body.model_name) { sendJSONResponse(res, 400, { success: false, error: 'Missing model_name' }); return true; }
            return await proxyToBackend(res, '/manage/models/download', 'POST', body);
        }
        if (urlPath.match(/^\/api\/model-switch\/download\/([^/]+)\/status$/) && method === 'GET') {
            const taskId = urlPath.split('/api/model-switch/download/')[1].replace('/status', '');
            return await proxyToBackend(res, `/manage/models/download/${taskId}/status`);
        }
        if (urlPath.match(/^\/api\/model-switch\/download\/([^/]+)\/retry$/) && method === 'POST') {
            const taskId = urlPath.split('/api/model-switch/download/')[1].replace('/retry', '');
            return await proxyToBackend(res, `/manage/models/download/${taskId}/retry`, 'POST');
        }
        if (urlPath.match(/^\/api\/model-switch\/download\/([^/]+)$/) && method === 'DELETE') {
            const taskId = urlPath.split('/api/model-switch/download/')[1];
            return await proxyToBackend(res, `/manage/models/download/${taskId}`, 'DELETE');
        }
        if (urlPath === '/api/model-switch/downloads' && method === 'GET') {
            return await proxyToBackend(res, '/manage/models/downloads');
        }
        return false;
    } catch (error) {
        logger.error('[Model Switch API]', error.message);
        sendJSONResponse(res, 500, { success: false, error: error.message });
        return true;
    }
}

export async function handleEngineApiRoutes(method, urlPath, req, res, config) {
    if (!urlPath.startsWith('/api/engine')) return false;
    try {
        if (urlPath === '/api/engine/status' && method === 'GET') {
            sendJSONResponse(res, 200, engineManager.getLatestData());
            return true;
        }
        if (urlPath === '/api/engine/switch' && method === 'POST') {
            const body = await parseRequestBody(req);
            if (!body.model_name) { sendJSONResponse(res, 400, { success: false, error: 'Missing model_name' }); return true; }
            sendJSONResponse(res, 200, await engineManager.switchEngine(body.model_name, body.engine_type, body.port));
            return true;
        }
        if (urlPath === '/api/engine/config' && method === 'GET') {
            sendJSONResponse(res, 200, engineManager.getConfig());
            return true;
        }
        return false;
    } catch (error) {
        logger.error('[Engine API]', error.message);
        sendJSONResponse(res, 500, { success: false, error: error.message });
        return true;
    }
}

export async function handleHealthApiRoutes(method, urlPath, req, res, config) {
    if (!urlPath.startsWith('/api/health')) return false;
    try {
        if (urlPath === '/api/health' && method === 'GET') {
            return await proxyToBackend(res, '/health');
        }
        if (urlPath === '/api/health/detailed' && method === 'GET') {
            return await proxyToBackend(res, '/health/detailed');
        }
        if (urlPath === '/api/health/history' && method === 'GET') {
            return await proxyToBackend(res, '/health/history');
        }
        return false;
    } catch (error) {
        logger.error('[Health API]', error.message);
        sendJSONResponse(res, 500, { success: false, error: error.message });
        return true;
    }
}

export async function handleRateLimitApiRoutes(method, urlPath, req, res, config) {
    if (!urlPath.startsWith('/api/ratelimit')) return false;
    try {
        if (urlPath === '/api/ratelimit/config' && method === 'GET') {
            return await proxyToBackend(res, '/manage/ratelimit/config');
        }
        if (urlPath === '/api/ratelimit/config' && method === 'PUT') {
            const body = await parseRequestBody(req);
            return await proxyToBackend(res, '/manage/ratelimit/config', 'PUT', body);
        }
        if (urlPath === '/api/ratelimit/stats' && method === 'GET') {
            return await proxyToBackend(res, '/manage/ratelimit/stats');
        }
        return false;
    } catch (error) {
        logger.error('[RateLimit API]', error.message);
        sendJSONResponse(res, 500, { success: false, error: error.message });
        return true;
    }
}

export async function handleConfigApiRoutes(method, urlPath, req, res, config) {
    if (!urlPath.startsWith('/api/config')) return false;
    try {
        if (urlPath === '/api/config' && method === 'GET') {
            return await proxyToBackend(res, '/manage/config');
        }
        if (urlPath === '/api/config' && method === 'PUT') {
            const body = await parseRequestBody(req);
            return await proxyToBackend(res, '/manage/config', 'PUT', body);
        }
        return false;
    } catch (error) {
        logger.error('[Config API]', error.message);
        sendJSONResponse(res, 500, { success: false, error: error.message });
        return true;
    }
}
