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

function parsePortValue(value) {
    if (value == null || String(value).trim() === '') return null;
    const parsed = Number(value);
    if (!Number.isInteger(parsed) || parsed <= 0) return null;
    return parsed;
}

function sendJSONResponse(res, statusCode, data) {
    res.writeHead(statusCode, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(data));
}

function sendHTMLResponse(res, html) {
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(html);
}

function getRequestUrl(req, fallbackPath = '/') {
    return new URL(req.url || fallbackPath, 'http://localhost');
}

async function sendPluginScript(res, fileName) {
    try {
        const script = await fs.readFile(pathModule.join(pluginDir, fileName), 'utf8');
        res.writeHead(200, { 'Content-Type': 'application/javascript; charset=utf-8', 'Access-Control-Allow-Origin': '*' });
        res.end(script);
    } catch (error) {
        sendJSONResponse(res, 500, { success: false, error: 'Failed' });
    }
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
    if (method !== 'GET' || (urlPath !== '/__panel_html__' && urlPath !== '/__panel__')) return false;
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

export async function handleGPUDashboardScript(method, urlPath, req, res) {
    if (urlPath !== '/plugins/ai-os-manager/gpu-dashboard-ui.js') return false;
    if (method === 'HEAD') {
        res.writeHead(200, { 'Content-Type': 'application/javascript; charset=utf-8', 'Access-Control-Allow-Origin': '*' });
        res.end();
        return true;
    }
    if (method !== 'GET') return false;
    await sendPluginScript(res, 'gpu-dashboard-ui.js');
    return true;
}

export async function handleInjectScript(method, urlPath, req, res) {
    if (urlPath !== '/plugins/ai-os-manager/inject.js') return false;
    if (method === 'HEAD') {
        res.writeHead(200, { 'Content-Type': 'application/javascript; charset=utf-8', 'Access-Control-Allow-Origin': '*' });
        res.end();
        return true;
    }
    if (method !== 'GET') return false;
    try {
        const script = await fs.readFile(pathModule.join(pluginDir, 'inject.js'), 'utf8');
        res.writeHead(200, { 'Content-Type': 'application/javascript; charset=utf-8', 'Access-Control-Allow-Origin': '*' });
        res.end(script);
        return true;
    } catch (error) {
        sendJSONResponse(res, 500, { success: false, error: 'Failed' });
        return true;
    }
}

export async function handlePluginStyles(method, urlPath, req, res) {
    if (urlPath !== '/plugins/ai-os-manager/styles.css') return false;
    if (method === 'HEAD') {
        res.writeHead(200, { 'Content-Type': 'text/css; charset=utf-8', 'Access-Control-Allow-Origin': '*' });
        res.end();
        return true;
    }
    if (method !== 'GET') return false;
    try {
        const css = await fs.readFile(pathModule.join(pluginDir, 'styles.css'), 'utf8');
        res.writeHead(200, { 'Content-Type': 'text/css; charset=utf-8', 'Access-Control-Allow-Origin': '*' });
        res.end(css);
        return true;
    } catch (error) {
        sendJSONResponse(res, 500, { success: false, error: 'Failed' });
        return true;
    }
}

export async function handleGPUMonitorApiRoutes(method, urlPath, req, res, config) {
    const requestUrl = getRequestUrl(req, urlPath);
    const search = requestUrl.search || '';
    const query = new URLSearchParams(search);
    const requestParams = {};
    for (const [key, value] of query.entries()) {
        requestParams[key] = value;
    }
    if (!requestParams.time_range && requestParams.range) {
        requestParams.time_range = requestParams.range;
        query.set('time_range', requestParams.time_range);
    }
    const proxiedSearch = query.toString() ? `?${query.toString()}` : '';

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
        if (urlPath === '/api/gpu-monitor/history' && method === 'GET') {
            return await proxyToBackend(res, `/manage/gpu/history${proxiedSearch}`);
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
        const requestUrl = getRequestUrl(req, urlPath);
        const search = requestUrl.search || '';
        if (urlPath === '/api/model-switch/models' && method === 'GET') {
            sendJSONResponse(res, 200, await modelSwitchService.getModelsList());
            return true;
        }
        if (urlPath === '/api/model-switch/switch-status' && method === 'GET') {
            sendJSONResponse(res, 200, await modelSwitchService.getSwitchStatus());
            return true;
        }
        if (urlPath === '/api/model-switch/aggregated' && method === 'GET') {
            const refresh = requestUrl.searchParams.get('refresh') === 'true';
            sendJSONResponse(res, 200, await modelSwitchService.getAggregatedModels(refresh));
            return true;
        }
        if (urlPath === '/api/model-switch/search' && method === 'GET') {
            return await proxyToBackend(res, `/manage/models/search${search}`);
        }
        if (urlPath === '/api/model-switch/recommend' && method === 'GET') {
            return await proxyToBackend(res, `/manage/gpu/recommend${search}`);
        }
        if (urlPath === '/api/model-switch/memory-check' && method === 'GET') {
            return await proxyToBackend(res, '/manage/gpu/memory-check');
        }
        if (urlPath.match(/^\/api\/model-switch\/memory-check\/(.+)$/) && method === 'POST') {
            const modelName = decodeURIComponent(urlPath.split('/api/model-switch/memory-check/')[1]);
            const body = await parseRequestBody(req);
            return await proxyToBackend(res, `/manage/gpu/memory-check/${encodeURIComponent(modelName)}`, 'POST', body);
        }
        if (urlPath === '/api/model-switch/pool' && method === 'GET') {
            return await proxyToBackend(res, `/manage/models/pool${search}`);
        }
        if (urlPath === '/api/model-switch/pool/register' && method === 'POST') {
            const body = await parseRequestBody(req);
            return await proxyToBackend(res, '/manage/models/pool/register', 'POST', body);
        }
        if (urlPath === '/api/model-switch/pool/sync-config' && method === 'POST') {
            return await proxyToBackend(res, '/manage/models/pool/sync-config', 'POST');
        }
        if (urlPath.match(/^\/api\/model-switch\/pool\/([^/]+)\/load$/) && method === 'POST') {
            const modelKey = decodeURIComponent(urlPath.split('/api/model-switch/pool/')[1].replace('/load', ''));
            const body = await parseRequestBody(req);
            return await proxyToBackend(res, `/manage/models/pool/${encodeURIComponent(modelKey)}/load`, 'POST', body);
        }
        if (urlPath.match(/^\/api\/model-switch\/pool\/([^/]+)$/) && method === 'GET') {
            const modelKey = decodeURIComponent(urlPath.split('/api/model-switch/pool/')[1]);
            return await proxyToBackend(res, `/manage/models/pool/${encodeURIComponent(modelKey)}`);
        }
        if (urlPath.match(/^\/api\/model-switch\/pool\/([^/]+)$/) && method === 'DELETE') {
            const modelKey = decodeURIComponent(urlPath.split('/api/model-switch/pool/')[1]);
            return await proxyToBackend(res, `/manage/models/pool/${encodeURIComponent(modelKey)}${search}`, 'DELETE');
        }
        if (urlPath === '/api/model-switch/default' && method === 'GET') {
            return await proxyToBackend(res, '/manage/default-model');
        }
        if (urlPath === '/api/model-switch/default' && method === 'POST') {
            const body = await parseRequestBody(req);
            if (!body.modelName) { sendJSONResponse(res, 400, { success: false, error: 'Missing modelName' }); return true; }
            return await proxyToBackend(res, `/manage/default-model/${encodeURIComponent(body.modelName)}`, 'POST');
        }
        if (urlPath === '/api/model-switch/default' && method === 'DELETE') {
            return await proxyToBackend(res, '/manage/default-model', 'DELETE');
        }
        if (urlPath === '/api/model-switch/preload' && method === 'GET') {
            return await proxyToBackend(res, '/manage/preload/status');
        }
        if (urlPath.match(/^\/api\/model-switch\/preload\/([^/]+)\/enable$/) && method === 'POST') {
            const modelName = decodeURIComponent(urlPath.split('/api/model-switch/preload/')[1].replace('/enable', ''));
            return await proxyToBackend(res, `/manage/preload/${encodeURIComponent(modelName)}/enable`, 'POST');
        }
        if (urlPath.match(/^\/api\/model-switch\/preload\/([^/]+)\/disable$/) && method === 'POST') {
            const modelName = decodeURIComponent(urlPath.split('/api/model-switch/preload/')[1].replace('/disable', ''));
            return await proxyToBackend(res, `/manage/preload/${encodeURIComponent(modelName)}/disable`, 'POST');
        }
        if (urlPath.match(/^\/api\/model-switch\/vllm-params\/(.+)$/) && method === 'GET') {
            const modelName = decodeURIComponent(urlPath.split('/api/model-switch/vllm-params/')[1]);
            sendJSONResponse(res, 200, await modelSwitchService.getModelVLLMParams(modelName));
            return true;
        }
        if (urlPath.match(/^\/api\/model-switch\/vllm-params\/(.+)$/) && method === 'PUT') {
            const modelName = decodeURIComponent(urlPath.split('/api/model-switch/vllm-params/')[1]);
            const body = await parseRequestBody(req);
            sendJSONResponse(res, 200, await modelSwitchService.updateModelVLLMParams(modelName, body.vllm_params || body));
            return true;
        }
        if (urlPath === '/api/model-switch/switch' && method === 'POST') {
            const body = await parseRequestBody(req);
            if (!body.modelName) { sendJSONResponse(res, 400, { success: false, error: 'Missing modelName' }); return true; }
            const options = {};
            if (body.engineType) options.engineType = body.engineType;
            const rawPort = body.port;
            const parsedPort = parsePortValue(rawPort);
            if (parsedPort !== null) options.port = parsedPort;
            sendJSONResponse(res, 200, await modelSwitchService.switchModel(body.modelName, body.async !== false, options));
            return true;
        }
        if (urlPath === '/api/model-switch/task-status' && method === 'GET') {
            const taskId = requestUrl.searchParams.get('taskId');
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
            await engineManager.updateData();
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
            return await proxyToBackend(res, '/manage/engines/config');
        }
        if (urlPath === '/api/engine/config' && method === 'PUT') {
            const body = await parseRequestBody(req);
            return await proxyToBackend(res, '/manage/engines/config', 'PUT', body);
        }
        if (urlPath === '/api/engine/param-schema' && method === 'GET') {
            return await proxyToBackend(res, '/manage/engines/param-schema');
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
        if (urlPath === '/api/ratelimit/queue' && method === 'GET') {
            return await proxyToBackend(res, '/manage/queue');
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
        if (urlPath === '/api/config/reload' && method === 'POST') {
            return await proxyToBackend(res, '/manage/config/reload', 'POST');
        }
        if (urlPath === '/api/config/operation-log' && method === 'GET') {
            return await proxyToBackend(res, '/manage/config/operation-log');
        }
        return false;
    } catch (error) {
        logger.error('[Config API]', error.message);
        sendJSONResponse(res, 500, { success: false, error: error.message });
        return true;
    }
}
