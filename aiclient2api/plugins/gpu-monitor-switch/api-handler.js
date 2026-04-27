/**
 * API 路由处理模块
 * 
 * 提供 REST API 接口：
 * - GPU 监控相关接口
 * - 模型切换相关接口
 * - UI 页面接口
 */

import { gpuMonitorService } from './gpu-monitor.js';
import { modelSwitchService } from './model-switch.js';
import logger from '../../utils/logger.js';
import fs from 'fs/promises';
import pathModule from 'path';

/**
 * 解析 JSON 请求体
 */
function parseRequestBody(req) {
    return new Promise((resolve, reject) => {
        let body = '';
        req.on('data', chunk => {
            body += chunk.toString();
        });
        req.on('end', () => {
            try {
                resolve(body ? JSON.parse(body) : {});
            } catch (error) {
                reject(error);
            }
        });
        req.on('error', reject);
    });
}

/**
 * 发送 JSON 响应
 */
function sendJSONResponse(res, statusCode, data) {
    res.writeHead(statusCode, { 
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*'
    });
    res.end(JSON.stringify(data));
}

/**
 * 发送 HTML 响应
 */
function sendHTMLResponse(res, html) {
    res.writeHead(200, { 
        'Content-Type': 'text/html; charset=utf-8',
        'Access-Control-Allow-Origin': '*'
    });
    res.end(html);
}

/**
 * GPU 监控 UI 路由处理
 */
export async function handleGPUMonitorUIRoute(method, urlPath, req, res, config) {
    if (method !== 'GET' || urlPath !== '/gpu-monitor.html') return false;
    
    try {
        const pluginDir = pathModule.join(process.cwd(), 'src', 'plugins', 'gpu-monitor-switch');
        const htmlPath = pathModule.join(pluginDir, 'gpu-monitor.html');
        const html = await fs.readFile(htmlPath, 'utf8');
        sendHTMLResponse(res, html);
        return true;
    } catch (error) {
        logger.error('[GPU Monitor UI] Failed to load HTML:', error.message);
        sendJSONResponse(res, 500, {
            success: false,
            error: 'Failed to load page'
        });
        return true;
    }
}

/**
 * 获取原版面板 HTML（内部 API）
 */
export async function handleGetPanelHTML(method, urlPath, req, res, config) {
    if (method !== 'GET' || urlPath !== '/__panel_html__') return false;
    
    try {
        const fs = await import('fs/promises');
        const pathModule = await import('path');
        const basePath = pathModule.default.join(process.cwd(), 'static');
        const indexPath = pathModule.default.join(basePath, 'index.html');
        const html = await fs.default.readFile(indexPath, 'utf8');
        
        res.writeHead(200, { 
            'Content-Type': 'text/html; charset=utf-8',
        });
        res.end(html);
        return true;
    } catch (error) {
        logger.error('[Panel HTML] Failed to read index.html:', error.message);
        res.writeHead(404);
        res.end('Panel not found');
        return true;
    }
}

/**
 * 管理面板入口路由 - 包含原版面板内容 + 注入脚本
 */
export async function handlePanelRoute(method, urlPath, req, res, config) {
    if (method !== 'GET' || urlPath !== '/gpu-admin') return false;
    
    try {
        const fs = await import('fs/promises');
        const pathModule = await import('path');
        const basePath = pathModule.default.join(process.cwd(), 'static');
        const indexPath = pathModule.default.join(basePath, 'index.html');
        let html = await fs.default.readFile(indexPath, 'utf8');
        
        // 注入插件脚本
        const injectScript = `<script src="/plugins/gpu-monitor-switch/inject.js" defer></script>`;
        if (html.includes('</body>')) {
            html = html.replace('</body>', injectScript + '</body>');
        } else {
            html += injectScript;
        }
        
        res.writeHead(200, { 
            'Content-Type': 'text/html; charset=utf-8',
            'Content-Length': Buffer.byteLength(html),
        });
        res.end(html);
        return true;
    } catch (error) {
        logger.error('[GPU Admin Panel] Failed to load panel:', error.message);
        res.writeHead(500, { 'Content-Type': 'text/html; charset=utf-8' });
        res.end(`<h1>Panel Error</h1><p>${error.message}</p>`);
        return true;
    }
}

/**
 * 注入脚本路由处理
 */
export async function handleInjectScript(method, urlPath, req, res, config) {
    if (method !== 'GET' || urlPath !== '/plugins/gpu-monitor-switch/inject.js') return false;
    
    try {
        const pluginDir = pathModule.join(process.cwd(), 'src', 'plugins', 'gpu-monitor-switch');
        const jsPath = pathModule.join(pluginDir, 'inject.js');
        const content = await fs.readFile(jsPath, 'utf8');
        res.writeHead(200, { 
            'Content-Type': 'application/javascript; charset=utf-8',
            'Cache-Control': 'no-cache',
        });
        res.end(content);
        return true;
    } catch (error) {
        logger.error('[GPU Monitor Inject] Failed to load script:', error.message);
        res.writeHead(500, { 'Content-Type': 'application/javascript' });
        res.end('console.error("Failed to load GPU monitor inject script");');
        return true;
    }
}

/**
 * 注入样式路由处理
 */
export async function handlePluginStyles(method, urlPath, req, res, config) {
    if (method !== 'GET' || urlPath !== '/plugins/gpu-monitor-switch/styles.css') return false;
    
    try {
        const pluginDir = pathModule.join(process.cwd(), 'src', 'plugins', 'gpu-monitor-switch');
        const cssPath = pathModule.join(pluginDir, 'styles.css');
        const content = await fs.readFile(cssPath, 'utf8');
        res.writeHead(200, { 
            'Content-Type': 'text/css; charset=utf-8',
            'Cache-Control': 'no-cache',
        });
        res.end(content);
        return true;
    } catch (error) {
        logger.error('[GPU Monitor Styles] Failed to load CSS:', error.message);
        res.writeHead(500, { 'Content-Type': 'text/css' });
        res.end('');
        return true;
    }
}

/**
 * GPU 监控 API 路由处理
 */
export async function handleGPUMonitorApiRoutes(method, path, req, res, config) {
    try {
        // 获取实时 GPU 信息
        if (path === '/api/gpu-monitor/info' && method === 'GET') {
            const result = await gpuMonitorService.getGPUInfoSync();
            sendJSONResponse(res, 200, result);
            return true;
        }

        // 获取缓存的 GPU 数据
        if (path === '/api/gpu-monitor' && method === 'GET') {
            const result = gpuMonitorService.getLatestGPUData();
            sendJSONResponse(res, 200, result);
            return true;
        }

        // 获取监控状态
        if (path === '/api/gpu-monitor/status' && method === 'GET') {
            const result = gpuMonitorService.getMonitoringStatus();
            sendJSONResponse(res, 200, result);
            return true;
        }

        // 设置监控间隔
        if (path === '/api/gpu-monitor/interval' && method === 'POST') {
            const body = await parseRequestBody(req);
            const result = gpuMonitorService.setMonitoringInterval(body.interval);
            const statusCode = result.success ? 200 : 400;
            sendJSONResponse(res, statusCode, result);
            return true;
        }

        // 启动监控
        if (path === '/api/gpu-monitor/start' && method === 'POST') {
            gpuMonitorService.startMonitoring();
            sendJSONResponse(res, 200, { 
                success: true, 
                message: 'GPU monitoring started' 
            });
            return true;
        }

        // 停止监控
        if (path === '/api/gpu-monitor/stop' && method === 'POST') {
            gpuMonitorService.stopMonitoring();
            sendJSONResponse(res, 200, { 
                success: true, 
                message: 'GPU monitoring stopped' 
            });
            return true;
        }

        return false;
    } catch (error) {
        logger.error('[GPU Monitor API] Error:', error.message);
        sendJSONResponse(res, 500, {
            success: false,
            error: error.message
        });
        return true;
    }
}

/**
 * 模型切换 API 路由处理
 */
export async function handleModelSwitchApiRoutes(method, path, req, res, config) {
    try {
        // 获取所有 provider pools
        if (path === '/api/model-switch/providers' && method === 'GET') {
            const result = modelSwitchService.getProviderPools();
            sendJSONResponse(res, 200, result);
            return true;
        }

        // 获取可用模型列表
        if (path === '/api/model-switch/models' && method === 'GET') {
            const url = new URL(req.url, `http://${req.headers.host}`);
            const providerName = url.searchParams.get('provider');
            const customName = url.searchParams.get('custom');

            if (!providerName) {
                sendJSONResponse(res, 400, {
                    success: false,
                    error: 'Missing required parameter: provider'
                });
                return true;
            }

            const result = await modelSwitchService.getAvailableModels(providerName, customName);
            const statusCode = result.success ? 200 : 400;
            sendJSONResponse(res, statusCode, result);
            return true;
        }

        // 切换模型
        if (path === '/api/model-switch/switch' && method === 'POST') {
            const body = await parseRequestBody(req);
            
            if (!body.provider || !body.customName || !body.newModel) {
                sendJSONResponse(res, 400, {
                    success: false,
                    error: 'Missing required parameters: provider, customName, newModel'
                });
                return true;
            }

            const result = await modelSwitchService.switchModel(
                body.provider,
                body.customName,
                body.newModel
            );
            const statusCode = result.success ? 200 : 400;
            sendJSONResponse(res, statusCode, result);
            return true;
        }

        // 刷新 provider
        if (path === '/api/model-switch/refresh' && method === 'POST') {
            const body = await parseRequestBody(req);
            
            if (!body.provider || !body.customName) {
                sendJSONResponse(res, 400, {
                    success: false,
                    error: 'Missing required parameters: provider, customName'
                });
                return true;
            }

            const result = await modelSwitchService.refreshProvider(
                body.provider,
                body.customName
            );
            const statusCode = result.success ? 200 : 400;
            sendJSONResponse(res, statusCode, result);
            return true;
        }

        // 重新加载配置
        if (path === '/api/model-switch/reload' && method === 'POST') {
            await modelSwitchService.loadPoolsConfig();
            sendJSONResponse(res, 200, {
                success: true,
                message: 'Configuration reloaded'
            });
            return true;
        }

        return false;
    } catch (error) {
        logger.error('[Model Switch API] Error:', error.message);
        sendJSONResponse(res, 500, {
            success: false,
            error: error.message
        });
        return true;
    }
}
