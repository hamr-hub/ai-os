import { gpuMonitorService } from './gpu-monitor.js';
import { modelSwitchService } from './model-switch.js';
import { backendClient } from './backend-client.js';
import logger from '../../utils/logger.js';
import fs from 'fs/promises';
import pathModule from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = pathModule.dirname(__filename);
const pluginDir = __dirname;
const staticDir = pathModule.resolve(process.cwd(), 'static');

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
    res.writeHead(statusCode, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
    res.end(JSON.stringify(data));
}

function sendHTMLResponse(res, html) {
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Access-Control-Allow-Origin': '*' });
    res.end(html);
}

export async function handleGPUMonitorUIRoute(method, urlPath, req, res, config) {
    if (method !== 'GET' || urlPath !== '/gpu-monitor.html') return false;
    try {
        const html = await fs.readFile(pathModule.join(pluginDir, 'gpu-monitor.html'), 'utf8');
        sendHTMLResponse(res, html);
        return true;
    } catch (error) {
        logger.error('[GPU Monitor UI]', error.message);
        sendJSONResponse(res, 500, { success: false, error: 'Failed' });
        return true;
    }
}

export async function handleGetPanelHTML(method, urlPath, req, res, config) {
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

export async function handlePanelRoute(method, urlPath, req, res, config) {
    if (method !== 'GET' || urlPath !== '/gpu-admin') return false;
    try {
        let html = await fs.readFile(pathModule.join(staticDir, 'index.html'), 'utf8');
        const injectScript = '<script src="/plugins/gpu-monitor-switch/inject.js" defer></script>';
        if (html.includes('</body>')) html = html.replace('</body>', injectScript + '</body>');
        else html += injectScript;
        res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Content-Length': Buffer.byteLength(html) });
        res.end(html);
        return true;
    } catch (error) {
        res.writeHead(500, { 'Content-Type': 'text/html' });
        res.end(`<h1>Error</h1><p>${error.message}</p>`);
        return true;
    }
}

export async function handleInjectScript(method, urlPath, req, res, config) {
    if (method !== 'GET' || urlPath !== '/plugins/gpu-monitor-switch/inject.js') return false;
    try {
        const content = await fs.readFile(pathModule.join(pluginDir, 'inject.js'), 'utf8');
        res.writeHead(200, { 'Content-Type': 'application/javascript; charset=utf-8', 'Cache-Control': 'no-cache' });
        res.end(content);
        return true;
    } catch (error) {
        logger.error('[GPU Monitor Inject]', error.message);
        res.writeHead(500, { 'Content-Type': 'application/javascript' });
        res.end('console.error("Failed to load inject.js");');
        return true;
    }
}

export async function handlePluginStyles(method, urlPath, req, res, config) {
    if (method !== 'GET' || urlPath !== '/plugins/gpu-monitor-switch/styles.css') return false;
    try {
        const content = await fs.readFile(pathModule.join(pluginDir, 'styles.css'), 'utf8');
        res.writeHead(200, { 'Content-Type': 'text/css; charset=utf-8', 'Cache-Control': 'no-cache' });
        res.end(content);
        return true;
    } catch (error) {
        logger.error('[GPU Monitor Styles]', error.message);
        res.writeHead(500, { 'Content-Type': 'text/css' });
        res.end('');
        return true;
    }
}

export async function handleGPUMonitorApiRoutes(method, path, req, res, config) {
    if (path !== '/api/gpu-monitor' && path !== '/api/gpu-monitor/info' && path !== '/api/gpu-monitor/status' && path !== '/api/gpu-monitor/interval' && path !== '/api/gpu-monitor/start' && path !== '/api/gpu-monitor/stop' && path !== '/api/gpu-monitor/backend-status') return false;
    try {
        if (path === '/api/gpu-monitor/backend-status' && method === 'GET') {
            sendJSONResponse(res, 200, { success: true, data: backendClient.getStatus() });
            return true;
        }
        if (path === '/api/gpu-monitor/info' && method === 'GET') {
            await gpuMonitorService.updateGPUData();
            sendJSONResponse(res, 200, { success: true, data: gpuMonitorService.gpuData, timestamp: new Date().toISOString() });
            return true;
        }
        if (path === '/api/gpu-monitor' && method === 'GET') {
            sendJSONResponse(res, 200, gpuMonitorService.getLatestGPUData());
            return true;
        }
        if (path === '/api/gpu-monitor/status' && method === 'GET') {
            sendJSONResponse(res, 200, gpuMonitorService.getMonitoringStatus());
            return true;
        }
        if (path === '/api/gpu-monitor/interval' && method === 'POST') {
            const body = await parseRequestBody(req);
            sendJSONResponse(res, 200, gpuMonitorService.setMonitoringInterval(body.interval));
            return true;
        }
        if (path === '/api/gpu-monitor/start' && method === 'POST') {
            gpuMonitorService.startMonitoring();
            sendJSONResponse(res, 200, { success: true, message: 'Started' });
            return true;
        }
        if (path === '/api/gpu-monitor/stop' && method === 'POST') {
            gpuMonitorService.stopMonitoring();
            sendJSONResponse(res, 200, { success: true, message: 'Stopped' });
            return true;
        }
        return false;
    } catch (error) {
        logger.error('[GPU Monitor API]', error.message);
        sendJSONResponse(res, 500, { success: false, error: error.message });
        return true;
    }
}

export async function handleModelSwitchApiRoutes(method, path, req, res, config) {
    if (path !== '/api/model-switch/models' && path !== '/api/model-switch/status' && path !== '/api/model-switch/switch' && path !== '/api/model-switch/start' && path !== '/api/model-switch/stop' && path !== '/api/model-switch/aggregated' && path !== '/api/model-switch/switch-status' && path !== '/api/model-switch/cancel' && !path.match(/^\/api\/model-switch\/vllm-params\/[^/]+$/)) return false;
    try {
        if (path === '/api/model-switch/models' && method === 'GET') {
            sendJSONResponse(res, 200, await modelSwitchService.getModelsList());
            return true;
        }
        if (path === '/api/model-switch/status' && method === 'GET') {
            const status = await modelSwitchService.getStatusFromBackend();
            sendJSONResponse(res, 200, { success: true, data: status });
            return true;
        }
        if (path === '/api/model-switch/switch-status' && method === 'GET') {
            sendJSONResponse(res, 200, { success: true, data: await modelSwitchService.getSwitchStatus() });
            return true;
        }
        if (path === '/api/model-switch/aggregated' && method === 'GET') {
            const refresh = req.url && req.url.includes('refresh=true');
            sendJSONResponse(res, 200, await modelSwitchService.getAggregatedModels(refresh));
            return true;
        }
        if (path.startsWith('/api/model-switch/vllm-params/') && method === 'GET') {
            const modelName = path.split('/api/model-switch/vllm-params/')[1];
            if (!modelName) { sendJSONResponse(res, 400, { success: false, error: 'Missing modelName' }); return true; }
            sendJSONResponse(res, 200, await modelSwitchService.getModelVLLMParams(modelName));
            return true;
        }
        if (path.startsWith('/api/model-switch/vllm-params/') && method === 'PUT') {
            const modelName = path.split('/api/model-switch/vllm-params/')[1];
            if (!modelName) { sendJSONResponse(res, 400, { success: false, error: 'Missing modelName' }); return true; }
            const body = await parseRequestBody(req);
            if (!body.vllmParams) { sendJSONResponse(res, 400, { success: false, error: 'Missing vllmParams' }); return true; }
            sendJSONResponse(res, 200, await modelSwitchService.updateModelVLLMParams(modelName, body.vllmParams));
            return true;
        }
        if (path === '/api/model-switch/switch' && method === 'POST') {
            const body = await parseRequestBody(req);
            if (!body.modelName) { sendJSONResponse(res, 400, { success: false, error: 'Missing modelName' }); return true; }
            sendJSONResponse(res, 200, await modelSwitchService.switchModel(body.modelName));
            return true;
        }
        if (path === '/api/model-switch/cancel' && method === 'POST') {
            sendJSONResponse(res, 200, await modelSwitchService.cancelSwitch());
            return true;
        }
        if (path === '/api/model-switch/start' && method === 'POST') {
            const body = await parseRequestBody(req);
            if (!body.modelName) { sendJSONResponse(res, 400, { success: false, error: 'Missing modelName' }); return true; }
            sendJSONResponse(res, 200, await modelSwitchService.startModel(body.modelName));
            return true;
        }
        if (path === '/api/model-switch/stop' && method === 'POST') {
            const body = await parseRequestBody(req);
            if (!body.modelName) { sendJSONResponse(res, 400, { success: false, error: 'Missing modelName' }); return true; }
            sendJSONResponse(res, 200, await modelSwitchService.stopModel(body.modelName));
            return true;
        }
        return false;
    } catch (error) {
        logger.error('[Model Switch API]', error.message);
        sendJSONResponse(res, 500, { success: false, error: error.message });
        return true;
    }
}
