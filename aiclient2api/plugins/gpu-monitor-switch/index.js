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

// 认证的 GPU 监控 API 路径（这些路径不需要 API Key 认证）
const GPU_MONITOR_API_PATHS = [
    '/api/gpu-monitor',
    '/api/model-switch',
    '/plugins/gpu-monitor-switch/inject.js',
];

/**
 * 插件定义
 */
const gpuMonitorSwitchPlugin = {
    name: 'gpu-monitor-switch',
    version: '1.0.0',
    description: 'GPU 监控与模型切换插件 - 实时监控 GPU 状态并支持模型切换',
    
    // 插件类型：认证插件，参与认证流程
    type: 'auth',
    
    // 优先级：数字越小越先执行
    _priority: 50,

    /**
     * 初始化钩子
     * @param {Object} config - 服务器配置
     */
    async init(config) {
        logger.info('[GPU Monitor Switch Plugin] Initializing...');
        await gpuMonitorService.init();
        await modelSwitchService.init();
        logger.info('[GPU Monitor Switch Plugin] Initialized successfully');
    },

    /**
     * 销毁钩子
     */
    async destroy() {
        logger.info('[GPU Monitor Switch Plugin] Destroying...');
        await gpuMonitorService.destroy();
        await modelSwitchService.destroy();
        logger.info('[GPU Monitor Switch Plugin] Destroyed successfully');
    },

    /**
     * 静态文件路径
     */
    staticPaths: [],

    /**
     * 路由定义
     */
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

    /**
     * 认证方法 - 允许 GPU 监控 API 路径绕过认证
     * @param {http.IncomingMessage} req - HTTP 请求
     * @param {http.ServerResponse} res - HTTP 响应
     * @param {URL} requestUrl - 解析后的 URL
     * @param {Object} config - 服务器配置
     * @returns {Promise<{handled: boolean, authorized: boolean|null}>}
     */
    async authenticate(req, res, requestUrl, config) {
        const pathname = requestUrl.pathname;
        
        // 对于 GPU 监控相关的 API 路径，直接授权
        for (const apiPath of GPU_MONITOR_API_PATHS) {
            if (pathname === apiPath || pathname.startsWith(apiPath + '/')) {
                return { handled: false, authorized: true };
            }
        }
        
        // 其他路径不处理，继续下一个认证插件
        return { handled: false, authorized: null };
    },

    /**
     * 中间件方法 - 用于注入菜单脚本到原版管理面板
     * @param {http.IncomingMessage} req - HTTP 请求
     * @param {http.ServerResponse} res - HTTP 响应
     * @param {URL} requestUrl - 解析后的 URL
     * @param {Object} config - 服务器配置
     * @returns {Promise<{handled: boolean}>}
     */
    async middleware(req, res, requestUrl, config) {
        const pathname = requestUrl.pathname;
        
        // 只对管理面板主页进行注入
        if (pathname !== '/' && pathname !== '/app' && pathname !== '/app/') {
            return { handled: false };
        }

        // 拦截响应，在 </body> 前注入脚本
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

    /**
     * 导出内部函数供外部使用
     */
    exports: {
        gpuMonitorService,
        modelSwitchService
    }
};

export default gpuMonitorSwitchPlugin;
