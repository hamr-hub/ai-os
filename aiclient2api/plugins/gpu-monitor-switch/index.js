/**
 * GPU 监控与模型切换插件
 * 
 * 功能：
 * 1. GPU 实时监控（使用率、显存、温度、功耗）
 * 2. 模型切换（切换 provider 使用的模型）
 * 3. Provider 管理（查看、刷新、启用/禁用）
 * 4. 动态注入菜单到 aiclient2api 原版管理面板
 */

import { gpuMonitorService } from './gpu-monitor.js';
import { modelSwitchService } from './model-switch.js';
import logger from '../../utils/logger.js';

import { handleGPUMonitorApiRoutes, handleModelSwitchApiRoutes, handleGPUMonitorUIRoute, handleInjectScript, handlePluginStyles, handlePanelRoute, handleGetPanelHTML } from './api-handler.js';

const EXEMPT_PATHS = [
    '/api/gpu-monitor',
    '/api/model-switch',
    '/plugins/gpu-monitor-switch/inject.js',
    '/plugins/gpu-monitor-switch/styles.css',
    '/gpu-admin',
    '/__panel_html__',
    '/gpu-monitor.html',
    '/health',
    '/favicon.ico',
    '/index.html',
    '/login.html',
];

const API_PATHS = ['/v1/', '/openai/'];

const gpuMonitorSwitchPlugin = {
    name: 'gpu-monitor-switch',
    version: '1.0.0',
    description: 'GPU 监控与模型切换插件 - 实时监控 GPU 状态并支持模型切换',
    
    type: 'auth',
    
    _priority: 50,

    async init(config) {
        logger.info('[GPU Monitor Switch Plugin] Initializing...');
        await gpuMonitorService.init();
        await modelSwitchService.init();
        logger.info('[GPU Monitor Switch Plugin] Initialized successfully');
    },

    async destroy() {
        logger.info('[GPU Monitor Switch Plugin] Destroying...');
        await gpuMonitorService.destroy();
        await modelSwitchService.destroy();
        logger.info('[GPU Monitor Switch Plugin] Destroyed successfully');
    },

    staticPaths: [],

    routes: [
        {
            method: 'GET',
            path: '/gpu-admin',
            handler: handlePanelRoute
        },
        {
            method: 'GET',
            path: '/__panel_html__',
            handler: handleGetPanelHTML
        },
        {
            method: 'GET',
            path: '/gpu-monitor.html',
            handler: handleGPUMonitorUIRoute
        },
        {
            method: 'GET',
            path: '/plugins/gpu-monitor-switch/inject.js',
            handler: handleInjectScript
        },
        {
            method: 'GET',
            path: '/plugins/gpu-monitor-switch/styles.css',
            handler: handlePluginStyles
        },
        {
            method: '*',
            path: '/api/gpu-monitor',
            handler: handleGPUMonitorApiRoutes
        },
        {
            method: '*',
            path: '/api/model-switch',
            handler: handleModelSwitchApiRoutes
        }
    ],

    async authenticate(req, res, requestUrl, config) {
        const pathname = requestUrl.pathname;
        
        for (const apiPath of EXEMPT_PATHS) {
            if (pathname === apiPath || pathname.startsWith(apiPath + '/')) {
                return { handled: false, authorized: true };
            }
        }
        
        for (const apiPath of API_PATHS) {
            if (pathname.startsWith(apiPath)) {
                const authHeader = req.headers['authorization'] || '';
                const apiKey = authHeader.startsWith('Bearer ') ? authHeader.slice(7) : null;
                
                const expectedApiKey = config.REQUIRED_API_KEY || '123456';
                
                if (apiKey && apiKey === expectedApiKey) {
                    logger.info('[GPU Monitor Switch Plugin] API key authenticated for:', pathname);
                    return { handled: false, authorized: true };
                } else {
                    logger.warn('[GPU Monitor Switch Plugin] Invalid API key for:', pathname);
                    res.writeHead(401, { 'Content-Type': 'application/json' });
                    res.end(JSON.stringify({
                        error: {
                            message: 'Unauthorized: API key is invalid or missing.',
                            type: 'authentication_error',
                            code: 'authentication_error'
                        }
                    }));
                    return { handled: true, authorized: false };
                }
            }
        }
        
        return { handled: false, authorized: null };
    },

    async middleware(req, res, requestUrl, config) {
        const pathname = requestUrl.pathname;
        
        if (pathname !== '/' && pathname !== '/app' && pathname !== '/app/') {
            return { handled: false };
        }

        const originalWriteHead = res.writeHead.bind(res);
        const originalEnd = res.end.bind(res);
        const chunks = [];

        res.writeHead = function(statusCode, statusMessage, headers) {
            return originalWriteHead(statusCode, statusMessage, headers);
        };

        res.write = function(chunk) {
            if (chunk) {
                chunks.push(Buffer.from(chunk));
            }
            return true;
        };

        res.end = function(chunk) {
            if (chunk) {
                chunks.push(Buffer.from(chunk));
            }

            let body = Buffer.concat(chunks).toString('utf8');
            const injectScript = `<script src="/plugins/gpu-monitor-switch/inject.js" defer></script>`;
            
            if (body.includes('</body>')) {
                body = body.replace('</body>', injectScript + '</body>');
            } else {
                body += injectScript;
            }

            res.writeHead(res.statusCode, {
                'Content-Type': 'text/html; charset=utf-8',
                'Content-Length': Buffer.byteLength(body),
            });
            originalEnd(body);
        };

        return { handled: false };
    },

    exports: {
        gpuMonitorService,
        modelSwitchService
    }
};

export default gpuMonitorSwitchPlugin;
