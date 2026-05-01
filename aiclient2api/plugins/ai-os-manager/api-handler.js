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
            if (!body.modelId) { sendJSONResponse(res, 400, { success: false, error: 'Missing modelId' }); return true; }
            const result = await backendClient.proxyRequest('/manage/models/download', 'POST', body);
            sendJSONResponse(res, 200, result);
            return true;
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
