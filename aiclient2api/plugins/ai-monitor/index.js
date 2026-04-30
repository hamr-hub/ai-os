import logger from '../../utils/logger.js';
import { statusService } from './status-service.js';
import fs from 'fs/promises';
import pathModule from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = pathModule.dirname(__filename);

const INJECT_TAG = '<script src="/plugins/ai-monitor/inject.js" defer></script>';
const STYLE_TAG = '<link rel="stylesheet" href="/plugins/ai-monitor/styles.css">';

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

function sendJSON(res, statusCode, data, config) {
    const headers = { 'Content-Type': 'application/json' };
    const origin = config?.CORS_ALLOWED_ORIGINS || '';
    if (origin) headers['Access-Control-Allow-Origin'] = origin;
    res.writeHead(statusCode, headers);
    res.end(JSON.stringify(data));
}

async function handleStatusApiRoutes(method, urlPath, req, res, config) {
    if (!urlPath.startsWith('/api/ai-monitor')) return false;
    try {
        if (urlPath === '/api/ai-monitor/status' && method === 'GET') {
            sendJSON(res, 200, statusService.getStatus());
            return true;
        }
        if (urlPath === '/api/ai-monitor/models' && method === 'GET') {
            sendJSON(res, 200, await statusService.getModelsList());
            return true;
        }
        if (urlPath === '/api/ai-monitor/engines' && method === 'GET') {
            sendJSON(res, 200, await statusService.getEnginesList());
            return true;
        }
        if (urlPath === '/api/ai-monitor/switch-model' && method === 'POST') {
            const body = await parseRequestBody(req);
            if (!body.model_name) {
                sendJSON(res, 400, { success: false, error: 'Missing model_name' });
                return true;
            }
            const options = {};
            if (body.engine_type) options.engine_type = body.engine_type;
            if (body.port) options.port = body.port;
            sendJSON(res, 200, await statusService.switchModel(body.model_name, options));
            return true;
        }
        if (urlPath === '/api/ai-monitor/switch-engine' && method === 'POST') {
            const body = await parseRequestBody(req);
            if (!body.model_name || !body.engine_type) {
                sendJSON(res, 400, { success: false, error: 'Missing model_name or engine_type' });
                return true;
            }
            sendJSON(res, 200, await statusService.switchEngine(body.model_name, body.engine_type, body.port));
            return true;
        }
        return false;
    } catch (error) {
        logger.error('[AI Monitor API]', error.message);
        sendJSON(res, 500, { success: false, error: error.message });
        return true;
    }
}

async function handleInjectScript(method, urlPath, req, res, config) {
    if (method !== 'GET' || urlPath !== '/plugins/ai-monitor/inject.js') return false;
    try {
        const script = await fs.readFile(pathModule.join(__dirname, 'inject.js'), 'utf8');
        res.writeHead(200, { 'Content-Type': 'application/javascript', 'Access-Control-Allow-Origin': '*' });
        res.end(script);
        return true;
    } catch (error) {
        sendJSON(res, 500, { success: false, error: 'Failed to load inject script' });
        return true;
    }
}

async function handlePluginStyles(method, urlPath, req, res, config) {
    if (method !== 'GET' || urlPath !== '/plugins/ai-monitor/styles.css') return false;
    try {
        const css = await fs.readFile(pathModule.join(__dirname, 'styles.css'), 'utf8');
        res.writeHead(200, { 'Content-Type': 'text/css', 'Access-Control-Allow-Origin': '*' });
        res.end(css);
        return true;
    } catch (error) {
        sendJSON(res, 500, { success: false, error: 'Failed to load styles' });
        return true;
    }
}

const aiMonitorPlugin = {
    name: 'ai-monitor',
    version: '2.0.0',
    description: 'AI 监控插件 - 接口全链路追踪 + 引擎/模型状态面板（显示当前引擎和运行模型，支持切换）',
    type: 'middleware',
    _priority: 100,

    streamCache: new Map(),

    async init(config) {
        await statusService.init();
        logger.info('[AI Monitor Plugin] v2.0 Initialized (with engine/model status panel)');
    },

    async destroy() {
        await statusService.destroy();
        logger.info('[AI Monitor Plugin] Destroyed');
    },

    routes: [
        { method: '*', path: '/api/ai-monitor', handler: handleStatusApiRoutes },
        { method: 'GET', path: '/plugins/ai-monitor/inject.js', handler: handleInjectScript },
        { method: 'GET', path: '/plugins/ai-monitor/styles.css', handler: handlePluginStyles },
    ],

    async middleware(req, res, requestUrl, config) {
        const pathname = requestUrl.pathname;

        if (pathname === '/' || pathname === '/app' || pathname === '/app/') {
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

                if (body.includes('</head>') && !body.includes('/plugins/ai-monitor/styles.css')) {
                    body = body.replace('</head>', STYLE_TAG + '</head>');
                }
                if (body.includes('</body>') && !body.includes('/plugins/ai-monitor/inject.js')) {
                    body = body.replace('</body>', INJECT_TAG + '</body>');
                } else if (!body.includes('/plugins/ai-monitor/inject.js')) {
                    body += INJECT_TAG;
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
        }

        const aiPaths = [
            '/v1/chat/completions',
            '/v1/responses',
            '/v1/messages',
            '/v1beta/models',
            '/v1/images/generations',
            '/v1/images/edits'
        ];
        const isAiPath = aiPaths.some(path => pathname.includes(path));

        if (isAiPath && req.method === 'POST' && !config._monitorRequestId) {
            const requestId = Date.now() + Math.random().toString(36).substring(2, 10);
            config._monitorRequestId = requestId;
        }

        return { handled: false };
    },

    hooks: {
        async onContentGenerated(config) {
            const { originalRequestBody, processedRequestBody, fromProvider, toProvider, model, _monitorRequestId, isStream } = config;
            if (!originalRequestBody) return;
            const traceRequestId = _monitorRequestId;

            setImmediate(() => {
                const hasConversion = JSON.stringify(originalRequestBody) !== JSON.stringify(processedRequestBody);
                logger.info(`[AI Monitor][${traceRequestId}] >>> Req Protocol: ${fromProvider}${hasConversion ? ' -> ' + toProvider : ''} | Model: ${model}`);

                if (hasConversion) {
                    logger.info(`[AI Monitor][${traceRequestId}] [Req Original]: ${JSON.stringify(originalRequestBody)}`);
                    logger.info(`[AI Monitor][${traceRequestId}] [Req Processed]: ${JSON.stringify(processedRequestBody)}`);
                } else {
                    logger.info(`[AI Monitor][${traceRequestId}] [Req]: ${JSON.stringify(originalRequestBody)}`);
                }
            });

            if (isStream && traceRequestId) {
                setTimeout(() => {
                    const cache = aiMonitorPlugin.streamCache.get(traceRequestId);
                    if (cache) {
                        const hasConversion = JSON.stringify(cache.nativeChunks) !== JSON.stringify(cache.convertedChunks);
                        logger.info(`[AI Monitor][${traceRequestId}] <<< Stream Response Aggregated: ${hasConversion ? cache.toProvider + ' -> ' : ''}${cache.fromProvider}`);

                        if (hasConversion) {
                            logger.info(`[AI Monitor][${traceRequestId}] [Res Native Full]: ${JSON.stringify(cache.nativeChunks)}`);
                            logger.info(`[AI Monitor][${traceRequestId}] [Res Converted Full]: ${JSON.stringify(cache.convertedChunks)}`);
                        } else {
                            logger.info(`[AI Monitor][${traceRequestId}] [Res Full]: ${JSON.stringify(cache.nativeChunks)}`);
                        }

                        aiMonitorPlugin.streamCache.delete(traceRequestId);
                    }
                }, 2000);
            }
        },

        async onUnaryResponse({ nativeResponse, clientResponse, fromProvider, toProvider, requestId }) {
            setImmediate(() => {
                const reqId = requestId || 'N/A';
                const hasConversion = JSON.stringify(nativeResponse) !== JSON.stringify(clientResponse);
                logger.info(`[AI Monitor][${reqId}] <<< Res Protocol: ${hasConversion ? toProvider + ' -> ' : ''}${fromProvider} (Unary)`);

                if (hasConversion) {
                    logger.info(`[AI Monitor][${reqId}] [Res Native]: ${JSON.stringify(nativeResponse)}`);
                    logger.info(`[AI Monitor][${reqId}] [Res Converted]: ${JSON.stringify(clientResponse)}`);
                } else {
                    logger.info(`[AI Monitor][${reqId}] [Res]: ${JSON.stringify(nativeResponse)}`);
                }
            });
        },

        async onStreamChunk({ nativeChunk, chunkToSend, fromProvider, toProvider, requestId }) {
            if (!requestId) return;

            if (!aiMonitorPlugin.streamCache.has(requestId)) {
                aiMonitorPlugin.streamCache.set(requestId, {
                    nativeChunks: [],
                    convertedChunks: [],
                    fromProvider,
                    toProvider
                });
            }

            const cache = aiMonitorPlugin.streamCache.get(requestId);

            if (nativeChunk != null) {
                if (Array.isArray(nativeChunk)) {
                    cache.nativeChunks.push(...nativeChunk.filter(item => item != null));
                } else {
                    cache.nativeChunks.push(nativeChunk);
                }
            }

            if (chunkToSend != null) {
                if (Array.isArray(chunkToSend)) {
                    cache.convertedChunks.push(...chunkToSend.filter(item => item != null));
                } else {
                    cache.convertedChunks.push(chunkToSend);
                }
            }
        },

        async onInternalRequestConverted({ requestId, internalRequest, converterName }) {
            setImmediate(() => {
                const reqId = requestId || 'N/A';
                logger.info(`[AI Monitor][${reqId}] >>> Internal Req Converted [${converterName}]: ${JSON.stringify(internalRequest)}`);
            });
        }
    },

    exports: {
        statusService,
    }
};

export default aiMonitorPlugin;
