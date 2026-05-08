import { gpuMonitorService } from './gpu-monitor.js';
import { modelSwitchService } from './model-switch.js';
import { engineManager } from './engine-manager.js';
import { backendClient } from './backend-client.js';
import logger from '../../utils/logger.js';
import fs from 'fs/promises';
import pathModule from 'path';

import {
    handleGPUMonitorApiRoutes,
    handleModelSwitchApiRoutes,
    handleEngineApiRoutes,
    handleHealthApiRoutes,
    handleRateLimitApiRoutes,
    handleConfigApiRoutes,
    handleInjectScript,
    handlePluginStyles,
    handlePanelRoute,
    handleGetPanelHTML,
} from './api-handler.js';

const INJECT_SCRIPT_TAG = '<script src="/plugins/ai-os-manager/inject.js" defer></script>';

const EXEMPT_PATHS = [
    '/plugins/ai-os-manager/inject.js',
    '/plugins/ai-os-manager/styles.css',
    '/gpu-admin',
    '/__panel_html__',
    '/health',
    '/favicon.ico',
    '/index.html',
    '/login.html',
    '/v1/models',
];

const ADMIN_API_PREFIXES = [
    '/api/gpu-monitor',
    '/api/model-switch',
    '/api/engine',
    '/api/health',
    '/api/ratelimit',
    '/api/config',
];

const API_PATHS = ['/v1/', '/openai/'];
const PROTECTED_API_PATHS = [
    '/v1/chat/completions',
    '/v1/completions',
    '/v1/embeddings',
];

let _staticInjected = false;

async function ensureInjectedStaticIndex() {
    if (_staticInjected) return;
    try {
        const indexPath = pathModule.resolve(process.cwd(), 'static', 'index.html');
        let html = await fs.readFile(indexPath, 'utf8');
        if (html.includes(INJECT_SCRIPT_TAG)) { _staticInjected = true; return; }
        html = html.includes('</body>') ? html.replace('</body>', INJECT_SCRIPT_TAG + '</body>') : html + INJECT_SCRIPT_TAG;
        await fs.writeFile(indexPath, html, 'utf8');
        _staticInjected = true;
        logger.info('[AI-OS Manager] Injected script tag into static/index.html');
    } catch (error) {
        logger.error('[AI-OS Manager] Failed to inject static index:', error.message);
    }
}

const aiOsManagerPlugin = {
    name: 'ai-os-manager',
    version: '3.0.0',
    description: 'AI-OS 管理插件 - GPU监控/模型管理',

    type: 'auth',
    _priority: 50,

    async init(config) {
        logger.info('[AI-OS Manager] Initializing...');
        await ensureInjectedStaticIndex();
        await gpuMonitorService.init();
        await modelSwitchService.init();
        await engineManager.init();
        logger.info('[AI-OS Manager] Initialized successfully');
    },

    async destroy() {
        logger.info('[AI-OS Manager] Destroying...');
        await gpuMonitorService.destroy();
        await modelSwitchService.destroy();
        await engineManager.destroy();
        logger.info('[AI-OS Manager] Destroyed');
    },

    routes: [
        { method: 'GET', path: '/gpu-admin', handler: handlePanelRoute },
        { method: 'GET', path: '/__panel_html__', handler: handleGetPanelHTML },
        { method: 'GET', path: '/plugins/ai-os-manager/inject.js', handler: handleInjectScript },
        { method: 'GET', path: '/plugins/ai-os-manager/styles.css', handler: handlePluginStyles },
        { method: '*', path: '/api/gpu-monitor', handler: handleGPUMonitorApiRoutes },
        { method: '*', path: '/api/model-switch', handler: handleModelSwitchApiRoutes },
        { method: '*', path: '/api/engine', handler: handleEngineApiRoutes },
        { method: '*', path: '/api/health', handler: handleHealthApiRoutes },
        { method: '*', path: '/api/ratelimit', handler: handleRateLimitApiRoutes },
        { method: '*', path: '/api/config', handler: handleConfigApiRoutes },
    ],

    async authenticate(req, res, requestUrl, config) {
        const pathname = requestUrl.pathname;

        for (const exemptPath of EXEMPT_PATHS) {
            if (pathname === exemptPath || pathname.startsWith(exemptPath + '/')) {
                return { handled: false, authorized: true };
            }
        }

        for (const prefix of ADMIN_API_PREFIXES) {
            if (pathname.startsWith(prefix)) {
                const authHeader = req.headers['authorization'] || '';
                const token = authHeader.startsWith('Bearer ') ? authHeader.slice(7) : req.headers['x-admin-token'] || null;
                const expectedToken = config.ADMIN_TOKEN || config.REQUIRED_API_KEY;
                if (!expectedToken) return { handled: false, authorized: true };
                if (!token || token !== expectedToken) {
                    res.writeHead(401, { 'Content-Type': 'application/json' });
                    res.end(JSON.stringify({ error: { message: 'Unauthorized - admin token required', type: 'authentication_error', code: 'authentication_error' } }));
                    return { handled: true, authorized: false };
                }
                return { handled: false, authorized: true };
            }
        }

        let isProtectedPath = false;
        for (const apiPath of PROTECTED_API_PATHS) {
            if (pathname === apiPath || pathname.startsWith(apiPath + '/')) {
                isProtectedPath = true; break;
            }
        }
        if (!isProtectedPath) return { handled: false, authorized: null };

        for (const apiPath of API_PATHS) {
            if (pathname.startsWith(apiPath)) {
                const authHeader = req.headers['authorization'] || '';
                const apiKey = authHeader.startsWith('Bearer ') ? authHeader.slice(7) : null;
                const expectedApiKey = config.REQUIRED_API_KEY;

                if (!expectedApiKey) return { handled: false, authorized: true };
                if (apiKey && apiKey === expectedApiKey) {
                    return { handled: false, authorized: true };
                } else {
                    res.writeHead(401, { 'Content-Type': 'application/json' });
                    res.end(JSON.stringify({ error: { message: 'Unauthorized', type: 'authentication_error', code: 'authentication_error' } }));
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
        let headersSent = false;

        res.writeHead = function(statusCode, statusMessage, headers) {
            headersSent = true;
            return originalWriteHead(statusCode, statusMessage, headers);
        };

        res.write = function(chunk) {
            if (chunk) chunks.push(Buffer.from(chunk));
            return true;
        };

        res.end = function(chunk, ...args) {
            if (chunk) chunks.push(Buffer.from(chunk));
            let body = Buffer.concat(chunks).toString('utf8');

            if (body.includes('</body>')) {
                body = body.replace('</body>', INJECT_SCRIPT_TAG + '</body>');
            } else {
                body += INJECT_SCRIPT_TAG;
            }

            if (!headersSent) {
                res.writeHead(res.statusCode, {
                    'Content-Type': 'text/html; charset=utf-8',
                    'Content-Length': Buffer.byteLength(body),
                });
            }
            originalEnd(body, ...args);
            return { handled: false };
        };

        return { handled: false };
    },

    exports: {
        gpuMonitorService,
        modelSwitchService,
        engineManager,
        backendClient,
    }
};

export default aiOsManagerPlugin;
