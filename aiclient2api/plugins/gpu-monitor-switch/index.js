/**
 * GPU 监控与模型切换插件
 * 
 * 功能：
 * 1. GPU 实时监控（使用率、显存、温度、功耗）
 * 2. 模型切换（切换 provider 使用的模型）
 * 3. Provider 管理（查看、刷新、启用/禁用）
 */

import { gpuMonitorService } from './gpu-monitor.js';
import { modelSwitchService } from './model-switch.js';
import logger from '../../utils/logger.js';

import { handleGPUMonitorApiRoutes, handleModelSwitchApiRoutes, handleGPUMonitorUIRoute } from './api-handler.js';

/**
 * 插件定义
 */
const gpuMonitorSwitchPlugin = {
    name: 'gpu-monitor-switch',
    version: '1.0.0',
    description: 'GPU 监控与模型切换插件 - 实时监控 GPU 状态并支持模型切换',
    
    // 插件类型：普通中间件插件
    type: 'middleware',
    
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
            path: '/gpu-monitor.html',
            handler: handleGPUMonitorUIRoute
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
     * 中间件方法
     * @param {http.IncomingMessage} req - HTTP 请求
     * @param {http.ServerResponse} res - HTTP 响应
     * @param {URL} requestUrl - 解析后的 URL
     * @param {Object} config - 服务器配置
     * @returns {Promise<{handled: boolean}>}
     */
    async middleware(req, res, requestUrl, config) {
        // 该插件不处理中间件逻辑，只路由
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
