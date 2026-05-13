(function() {
    const CSS_LINK = '<link rel="stylesheet" href="/plugins/ai-os-manager/styles.css">';
    const TOAST_CONTAINER = '<div class="aios-toast-container" id="aios-toast-container"></div>';

    (function migrateLegacyToken() {
        try {
            const legacyToken = localStorage.getItem('aios_admin_token');
            if (legacyToken && !localStorage.getItem('auth_token')) {
                localStorage.setItem('auth_token', legacyToken);
                localStorage.setItem('auth_user', 'admin');
                console.log('[AI-OS Manager] Migrated legacy admin token to auth_token');
            }
            localStorage.removeItem('aios_admin_token');
        } catch (_) {}
    })();

    function showTokenModal() {
        return new Promise((resolve) => {
            const overlay = document.createElement('div');
            overlay.className = 'aios-p-scope aios-p-modal-overlay';

            const modal = document.createElement('div');
            modal.className = 'aios-p-modal';

            const header = document.createElement('h3');
            header.textContent = 'API Key 验证';

            const desc = document.createElement('div');
            desc.style.cssText = 'font-size:12px;color:var(--aios-text-secondary);margin-bottom:12px;';
            desc.textContent = '请输入 API Key（与系统 REQUIRED_API_KEY 一致）';

            const input = document.createElement('input');
            input.className = 'aios-p-input';
            input.type = 'password';
            input.placeholder = '请输入 API Key';
            input.style.width = '100%';

            const errorMsg = document.createElement('div');
            errorMsg.style.cssText = 'display:none;font-size:12px;color:var(--aios-color-danger);margin-top:8px;';

            const actions = document.createElement('div');
            actions.className = 'aios-p-modal-actions';

            const cancelBtn = document.createElement('button');
            cancelBtn.className = 'aios-p-btn';
            cancelBtn.textContent = '取消';

            const submitBtn = document.createElement('button');
            submitBtn.className = 'aios-p-btn aios-p-btn-primary';
            submitBtn.textContent = '确认';

            actions.appendChild(cancelBtn);
            actions.appendChild(submitBtn);
            modal.appendChild(header);
            modal.appendChild(desc);
            modal.appendChild(input);
            modal.appendChild(errorMsg);
            modal.appendChild(actions);
            overlay.appendChild(modal);
            document.body.appendChild(overlay);

            input.focus();
            const cleanup = (value) => { overlay.remove(); resolve(value); };
            cancelBtn.onclick = () => cleanup(null);
            submitBtn.onclick = () => {
                if (!input.value || !input.value.trim()) {
                    errorMsg.textContent = '请输入有效的 Token';
                    errorMsg.style.display = 'block';
                    return;
                }
                cleanup(input.value.trim() || null);
            };
            input.onkeydown = (e) => {
                if (e.key === 'Enter') {
                    if (!input.value || !input.value.trim()) {
                        errorMsg.textContent = '请输入有效的 Token';
                        errorMsg.style.display = 'block';
                        return;
                    }
                    cleanup(input.value.trim() || null);
                }
                if (e.key === 'Escape') cleanup(null);
            };
        });
    }

    function adminFetch(url, options = {}) {
        const token = localStorage.getItem('auth_token') || '';
        const headers = { 'Content-Type': 'application/json', ...options.headers };
        if (token) headers['Authorization'] = 'Bearer ' + token;
        return fetch(url, { ...options, headers }).then(r => {
            if (r.status === 401) {
                return showTokenModal().then(newToken => {
                    if (newToken) {
                        localStorage.setItem('auth_token', newToken);
                        localStorage.setItem('auth_user', 'admin');
                        return adminFetch(url, options);
                    }
                    throw new Error('Unauthorized');
                });
            }
            return r.json();
        });
    }

    function showToast(message, type = 'info') {
        const container = document.getElementById('aios-toast-container');
        if (!container) return;
        const toast = document.createElement('div');
        toast.className = `aios-toast aios-toast-${type}`;
        toast.innerHTML = `<span>${escapeHtml(message)}</span><button class="aios-toast-close" onclick="this.parentElement.remove()">&times;</button>`;
        container.appendChild(toast);
        setTimeout(() => toast.remove(), 4000);
    }

    function loadingHTML(text = '加载中...') {
        return `<div class="aios-p-loading">${escapeHtml(text)}</div>`;
    }

    function emptyHTML(text = '暂无数据') {
        return `<div class="aios-p-empty"><i class="fas fa-inbox"></i><span>${escapeHtml(text)}</span></div>`;
    }

    function errorHTML(msg) {
        return `<div class="aios-p-error">${escapeHtml(msg)}</div>`;
    }

    function formatBytes(bytes) {
        if (!bytes || bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    function formatNumber(value, digits = 2) {
        if (value === null || value === undefined || value === '') return '-';
        const num = Number(value);
        return Number.isFinite(num) ? num.toFixed(digits) : String(value);
    }

    function escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function engineDisplayName(type) {
        if (!type) return '-';
        const t = type.toLowerCase();
        if (t === 'vllm') return 'vLLM';
        if (t === 'sglang') return 'SGLang';
        if (t === 'llamacpp' || t === 'llama_cpp') return 'llama.cpp';
        return type;
    }

    function normalizeEngineType(type) {
        const t = (type || '').toLowerCase();
        if (t === 'llama.cpp' || t === 'llamacpp') return 'llamacpp';
        return t || 'vllm';
    }

    function normalizeModelText(value) {
        const raw = String(value || '').trim();
        if (!raw) return '';
        return raw.split('/').filter(Boolean).pop().toLowerCase();
    }

    function parsePortValue(value) {
        if (value == null || String(value).trim() === '') return null;
        const parsed = Number(value);
        if (!Number.isInteger(parsed) || parsed <= 0) return null;
        return parsed;
    }

    function getResponseTextAsReason(result) {
        if (!result) return '';
        if (typeof result === 'string') return result;
        if (result.reason) return result.reason;
        if (result.error) return result.error;
        if (result.detail) return typeof result.detail === 'string' ? result.detail : '';
        if (result.message) return result.message;
        return '';
    }

    function normalizePortValue(value) {
        if (value == null) return null;
        const parsed = parsePortValue(value);
        return parsed === null ? null : parsed;
    }

    function getEngineServicesFromPayload(payload) {
        const source = payload || {};
        const data = source.data || source;
        return Array.isArray(data.services) ? data.services
            : Array.isArray(data.running_services) ? data.running_services
            : Array.isArray(data.engines) ? data.engines
            : [];
    }

    function showConfirm(message, options = {}) {
        const okLabel = options.okLabel || '确认';
        const cancelLabel = options.cancelLabel || '取消';
        const tip = String(message || '');
        return new Promise((resolve) => {
            const overlay = document.createElement('div');
            overlay.className = 'aios-p-modal-overlay';
            overlay.style.zIndex = '2147483001';

            const modal = document.createElement('div');
            modal.className = 'aios-p-modal';

            const title = document.createElement('h3');
            title.textContent = '请确认操作';

            const content = document.createElement('div');
            content.style.cssText = 'font-size:13px;line-height:1.6;color:var(--text-secondary);margin-bottom:14px;';
            content.textContent = tip;

            const actions = document.createElement('div');
            actions.className = 'aios-p-modal-actions';

            const cancelBtn = document.createElement('button');
            cancelBtn.className = 'aios-p-btn';
            cancelBtn.type = 'button';
            cancelBtn.textContent = cancelLabel;

            const confirmBtn = document.createElement('button');
            confirmBtn.className = 'aios-p-btn aios-p-btn-primary';
            confirmBtn.type = 'button';
            confirmBtn.textContent = okLabel;

            actions.appendChild(cancelBtn);
            actions.appendChild(confirmBtn);
            modal.appendChild(title);
            modal.appendChild(content);
            modal.appendChild(actions);
            overlay.appendChild(modal);
            document.body.appendChild(overlay);

            const cleanup = (value) => {
                overlay.remove();
                document.removeEventListener('keydown', onKeydown);
                resolve(value);
            };

            const onKeydown = (event) => {
                if (event.key === 'Escape') cleanup(false);
                if (event.key === 'Enter') cleanup(true);
            };

            document.addEventListener('keydown', onKeydown);
            cancelBtn.onclick = () => cleanup(false);
            confirmBtn.onclick = () => cleanup(true);
            overlay.onclick = (event) => {
                if (event.target === overlay) cleanup(false);
            };
            confirmBtn.focus();
        });
    }

    const GPU_HTML = `
<div class="aios-p-section" id="section-aios-gpu">
    <div class="aios-p-section-header">
        <h2><i class="fas fa-microchip"></i> GPU 监控</h2>
        <div class="aios-p-section-actions">
            <div class="aios-p-range-selector">
                <button class="aios-p-range-btn active" data-range="min" onclick="AiosManager.gpu.setTimeRange('min')">分钟</button>
                <button class="aios-p-range-btn" data-range="hour" onclick="AiosManager.gpu.setTimeRange('hour')">小时</button>
                <button class="aios-p-range-btn" data-range="day" onclick="AiosManager.gpu.setTimeRange('day')">天</button>
            </div>
            <button class="aios-p-btn aios-p-btn-sm" data-action="gpu-refresh"><i class="fas fa-sync-alt"></i> 刷新</button>
        </div>
    </div>
    <div id="aios-gpu-summary" class="aios-p-gpu-summary">${loadingHTML()}</div>
    <div class="aios-p-stats-grid" id="aios-gpu-stats">${loadingHTML()}</div>
    <div class="aios-p-gpu-layout" style="margin-top:var(--space-lg);">
        <div class="aios-p-card aios-p-chart-card">
            <div class="aios-p-card-header"><h3><i class="fas fa-chart-area"></i> GPU 历史趋势</h3></div>
            <div class="aios-p-card-content"><div id="aios-gpu-history">${loadingHTML()}</div></div>
        </div>
        <div class="aios-p-card aios-p-status-card">
            <div class="aios-p-card-header"><h3><i class="fas fa-bolt"></i> 引擎状态</h3></div>
            <div class="aios-p-card-content" id="aios-engine-status">${loadingHTML()}</div>
        </div>
    </div>
    <div class="aios-p-card aios-p-status-card" style="margin-top:var(--space-lg);">
        <div class="aios-p-card-header">
            <h3><i class="fas fa-sliders-h"></i> 引擎配置</h3>
            <button class="aios-p-btn aios-p-btn-sm" onclick="AiosManager.gpu.loadEngineConfig()"><i class="fas fa-sync-alt"></i> 刷新</button>
            <button class="aios-p-btn aios-p-btn-sm aios-p-btn-primary" onclick="AiosManager.gpu.saveEngineConfig()"><i class="fas fa-save"></i> 保存</button>
        </div>
        <div class="aios-p-card-content">
            <textarea id="aios-engine-config-editor" class="aios-p-input" style="min-height:180px;font-family:Menlo,monospace;resize:vertical;"></textarea>
        </div>
    </div>
</div>`;

    const MODEL_HTML = `
<div class="aios-p-section" id="section-aios-model">
    <div class="aios-p-section-header">
        <h2><i class="fas fa-cubes"></i> 模型管理</h2>
        <div class="aios-p-section-actions">
            <button class="aios-p-btn aios-p-btn-sm" data-action="model-refresh"><i class="fas fa-sync-alt"></i> 刷新</button>
        </div>
    </div>
    <div class="aios-p-status-banner" id="aios-model-banner">${loadingHTML()}</div>
    <div id="aios-p-switching-banner" style="margin-bottom:var(--space-lg);"></div>
    <div class="aios-p-card aios-p-action-card">
        <div class="aios-p-card-header"><h3><i class="fas fa-exchange-alt"></i> 快速切换</h3></div>
        <div class="aios-p-card-content">
            <div class="aios-p-form-grid">
                <div class="aios-p-form-group">
                    <label>模型</label>
                    <select id="aios-switch-model" class="aios-p-input aios-p-select"></select>
                </div>
                <div class="aios-p-form-group">
                    <label>引擎</label>
                    <select id="aios-switch-engine" class="aios-p-input aios-p-select">
                        <option value="vllm">vLLM</option>
                        <option value="sglang">SGLang</option>
                        <option value="llamacpp">llama.cpp</option>
                    </select>
                </div>
                <div class="aios-p-form-group">
                    <label>端口</label>
                    <input id="aios-switch-port" class="aios-p-input" type="number" placeholder="自动(8000)">
                </div>
                <div class="aios-p-form-actions">
                    <button class="aios-p-btn aios-p-btn-primary" data-action="switch-model"><i class="fas fa-play"></i> 切换</button>
                </div>
            </div>
            <div id="aios-switch-status" class="aios-p-action-status" style="margin-top:var(--space-md);"></div>
        </div>
    </div>
    <div class="aios-p-models-shell" style="margin-top:var(--space-lg);">
        <div id="aios-model-list">${loadingHTML()}</div>
    </div>
    <div class="aios-p-card aios-p-action-card" style="margin-top:var(--space-lg);">
        <div class="aios-p-card-header"><h3><i class="fas fa-search"></i> 模型搜索与显存优选</h3></div>
        <div class="aios-p-card-content">
            <div class="aios-p-form-grid">
                <div class="aios-p-form-group" style="flex:2;">
                    <label>关键词</label>
                    <input id="aios-search-keyword" class="aios-p-input" placeholder="如: qwen 7b awq">
                </div>
                <div class="aios-p-form-group">
                    <label>来源</label>
                    <select id="aios-search-source" class="aios-p-input aios-p-select">
                        <option value="all">全部</option>
                        <option value="modelscope">ModelScope</option>
                        <option value="hf">HuggingFace</option>
                        <option value="openxlab">OpenXLab</option>
                        <option value="local">本地</option>
                    </select>
                </div>
                <div class="aios-p-form-group">
                    <label>排序</label>
                    <select id="aios-search-sort" class="aios-p-input aios-p-select">
                        <option value="feasible">可运行优先</option>
                        <option value="required_gb">显存需求</option>
                        <option value="size">模型大小</option>
                        <option value="quant">量化</option>
                    </select>
                </div>
                <div class="aios-p-form-actions">
                    <button class="aios-p-btn aios-p-btn-primary" onclick="AiosManager.model.searchModels()"><i class="fas fa-search"></i> 搜索</button>
                    <button class="aios-p-btn" onclick="AiosManager.model.recommendModels()"><i class="fas fa-magic"></i> 优选</button>
                </div>
            </div>
            <div id="aios-search-results" style="margin-top:var(--space-lg);"></div>
        </div>
    </div>
    <div class="aios-p-card aios-p-action-card" style="margin-top:var(--space-lg);">
        <div class="aios-p-card-header"><h3><i class="fas fa-download"></i> 模型下载</h3></div>
        <div class="aios-p-card-content">
            <div class="aios-p-form-grid">
                <div class="aios-p-form-group" style="flex:2;">
                    <label>模型ID (HuggingFace / ModelScope / OpenXLab)</label>
                    <input id="aios-download-model-name" class="aios-p-input" placeholder="如: Qwen/Qwen2.5-7B-Instruct" style="width:100%;">
                </div>
                <div class="aios-p-form-group">
                    <label>来源</label>
                    <select id="aios-download-source" class="aios-p-input aios-p-select">
                        <option value="hf">HuggingFace</option>
                        <option value="ms">ModelScope</option>
                        <option value="openxlab">OpenXLab</option>
                    </select>
                </div>
                <div class="aios-p-form-actions">
                    <button class="aios-p-btn aios-p-btn-primary" data-action="download-model"><i class="fas fa-cloud-download-alt"></i> 下载</button>
                </div>
            </div>
            <div id="aios-download-tasks" style="margin-top:var(--space-lg);"></div>
        </div>
    </div>
    <div class="aios-p-card aios-p-action-card" style="margin-top:var(--space-lg);">
        <div class="aios-p-card-header">
            <h3><i class="fas fa-layer-group"></i> 模型池</h3>
            <button class="aios-p-btn aios-p-btn-sm" onclick="AiosManager.model.refreshPool()"><i class="fas fa-sync-alt"></i> 刷新</button>
            <button class="aios-p-btn aios-p-btn-sm" onclick="AiosManager.model.syncPoolConfig()"><i class="fas fa-save"></i> 同步配置</button>
        </div>
        <div class="aios-p-card-content" id="aios-model-pool">${loadingHTML()}</div>
    </div>
</div>`;

    const HEALTH_HTML = `
<div class="aios-p-section" id="section-aios-health">
    <div class="aios-p-section-header">
        <h2><i class="fas fa-heartbeat"></i> 健康运维</h2>
        <div class="aios-p-section-actions">
            <button class="aios-p-btn aios-p-btn-sm" data-action="health-refresh"><i class="fas fa-sync-alt"></i> 刷新</button>
        </div>
    </div>
    <div class="aios-p-status-banner" id="aios-health-banner">${loadingHTML()}</div>
    <div class="aios-p-card" style="margin-top:var(--space-lg);">
        <div class="aios-p-card-header"><h3><i class="fas fa-stethoscope"></i> 详细检查</h3></div>
        <div class="aios-p-card-content" id="aios-health-details">${loadingHTML()}</div>
    </div>
    <div class="aios-p-card" style="margin-top:var(--space-lg);">
        <div class="aios-p-card-header"><h3><i class="fas fa-history"></i> 历史摘要</h3></div>
        <div class="aios-p-card-content" id="aios-health-history">${loadingHTML()}</div>
    </div>
</div>`;

    const RATELIMIT_HTML = `
<div class="aios-p-section" id="section-aios-ratelimit">
    <div class="aios-p-section-header">
        <h2><i class="fas fa-tachometer-alt"></i> 限流控制</h2>
        <div class="aios-p-section-actions">
            <button class="aios-p-btn aios-p-btn-sm" onclick="AiosManager.ratelimit.refresh()"><i class="fas fa-sync-alt"></i> 刷新</button>
            <button class="aios-p-btn aios-p-btn-sm aios-p-btn-primary" onclick="AiosManager.ratelimit.save()"><i class="fas fa-save"></i> 保存</button>
        </div>
    </div>
    <div class="aios-p-stats-grid" id="aios-ratelimit-stats">${loadingHTML()}</div>
    <div class="aios-p-card" style="margin-top:var(--space-lg);">
        <div class="aios-p-card-header"><h3><i class="fas fa-sliders-h"></i> 限流配置</h3></div>
        <div class="aios-p-card-content">
            <div class="aios-p-form-grid">
                <div class="aios-p-form-group">
                    <label>IP QPS 限制</label>
                    <input id="aios-rl-ip-limit" class="aios-p-input" type="number" min="0">
                </div>
                <div class="aios-p-form-group">
                    <label>统计窗口(秒)</label>
                    <input id="aios-rl-window" class="aios-p-input" type="number" min="1">
                </div>
                <div class="aios-p-form-group">
                    <label>并发上限</label>
                    <input id="aios-rl-concurrency" class="aios-p-input" type="number" min="1">
                </div>
                <div class="aios-p-form-group">
                    <label>流式并发上限</label>
                    <input id="aios-rl-stream-concurrency" class="aios-p-input" type="number" min="1">
                </div>
                <div class="aios-p-form-group">
                    <label>排队超时(秒)</label>
                    <input id="aios-rl-timeout" class="aios-p-input" type="number" min="1">
                </div>
                <div class="aios-p-form-group">
                    <label>队列上限</label>
                    <input id="aios-rl-max-queue" class="aios-p-input" type="number" min="0">
                </div>
                <div class="aios-p-form-group">
                    <label>每分钟 Token 上限</label>
                    <input id="aios-rl-token-limit" class="aios-p-input" type="number" min="0">
                </div>
                <div class="aios-p-form-group">
                    <label>最大上下文 Token</label>
                    <input id="aios-rl-max-model-len" class="aios-p-input" type="number" min="1">
                </div>
                <div class="aios-p-form-group" style="flex:1 1 100%;">
                    <label>白名单 IP（逗号分隔）</label>
                    <input id="aios-rl-whitelist" class="aios-p-input" type="text" placeholder="127.0.0.1,localhost">
                </div>
                <div class="aios-p-form-group" style="flex:1 1 100%;">
                    <label>限流路径（逗号分隔）</label>
                    <input id="aios-rl-paths" class="aios-p-input" type="text" placeholder="/v1/chat/completions,/v1/embeddings">
                </div>
            </div>
        </div>
    </div>
</div>`;

    const CONFIG_HTML = `
<div class="aios-p-section" id="section-aios-config">
    <div class="aios-p-section-header">
        <h2><i class="fas fa-cog"></i> 配置中心</h2>
        <div class="aios-p-section-actions">
            <button class="aios-p-btn aios-p-btn-sm" onclick="AiosManager.config.refresh()"><i class="fas fa-sync-alt"></i> 刷新</button>
            <button class="aios-p-btn aios-p-btn-sm" onclick="AiosManager.config.reload()"><i class="fas fa-redo"></i> 重载</button>
            <button class="aios-p-btn aios-p-btn-sm aios-p-btn-primary" onclick="AiosManager.config.save()"><i class="fas fa-save"></i> 保存</button>
        </div>
    </div>
    <div class="aios-p-card">
        <div class="aios-p-card-header"><h3><i class="fas fa-file-code"></i> 当前配置</h3></div>
        <div class="aios-p-card-content">
            <textarea id="aios-config-editor" class="aios-p-input" style="min-height:360px;font-family:Menlo,monospace;resize:vertical;"></textarea>
        </div>
    </div>
    <div class="aios-p-card" style="margin-top:var(--space-lg);">
        <div class="aios-p-card-header"><h3><i class="fas fa-history"></i> 操作日志</h3></div>
        <div class="aios-p-card-content" id="aios-config-operation-log">${loadingHTML()}</div>
    </div>
</div>`;

    let initialized = false;
    let aiosScope = null;

    const AIOS_SECTIONS = ['aios-gpu', 'aios-model'];

    function findNavigationContainer() {
        const selectors = [
            '.sidebar .nav-container',
            '.sidebar-inner .nav-container',
            '.nav-container',
            '.sidebar-nav',
            '#sidebar-container nav',
            '#sidebar-container .nav-container',
            '#sidebar-container',
            '#sidebar',
            '.sidebar nav',
            '.sidebar',
            'aside nav',
            'aside',
            'nav.sidebar-nav',
            'nav',
            '[class*="sidebar"] nav',
            '[class*="sidebar"]',
            '[class*="nav-sidebar"]',
            '[class*="side-nav"]',
            '[role="navigation"]'
        ];
        for (const selector of selectors) {
            const el = document.querySelector(selector);
            if (el && el.children.length > 0) return el;
        }
        return null;
    }

    function findContentContainer() {
        const selectors = [
            'main.app-main',
            '.app-main',
            '#content-container',
            'main#content-container',
            'main.content',
            '#content',
            '.content',
            'main',
            '[class*="content"]',
            '.container main',
            '.container'
        ];
        for (const selector of selectors) {
            const el = document.querySelector(selector);
            if (el) return el;
        }
        return document.body;
    }

    function getInitialAiosSection() {
        const hash = window.location.hash.slice(1);
        if (AIOS_SECTIONS.includes(hash)) return hash;

        const path = window.location.pathname;
        if (path === '/gpu-admin' || path === '/__panel_html__' || path === '/__panel__') {
            return 'aios-gpu';
        }
        return null;
    }

    function waitForDOM(cb) {
        let tries = 0;
        const maxTries = 200;
        let injected = false;
        
        function check() {
            if (injected) return;
            const nav = findNavigationContainer();
            const content = findContentContainer();
            if (nav && content) {
                injected = true;
                cb(nav, content);
                return;
            }
            tries++;
            if (tries < maxTries) {
                setTimeout(check, 500);
            } else {
                    console.warn('[AI-OS Manager] Could not find DOM containers after maximum attempts');
                    cb(null, document.body);
                }
        }
        check();
        
        window.addEventListener('load', () => {
            if (!injected) setTimeout(check, 1000);
        });
        
        if (typeof MutationObserver !== 'undefined') {
            const observer = new MutationObserver(() => {
                if (!injected) check();
                else observer.disconnect();
            });
            observer.observe(document.body, { childList: true, subtree: true });
        }
    }

    function hideNativeSections() {
        document.querySelectorAll('.section.active').forEach(el => {
            if (!el.id || !el.id.startsWith('section-aios-')) {
                el.classList.remove('active');
            }
        });
        document.querySelectorAll('.nav-item.active').forEach(el => {
            if (!el.id || !el.id.startsWith('nav-aios-')) {
                el.classList.remove('active');
            }
        });
    }

    function shouldHideHostSiblings(host) {
        if (!host || host === document.body) return false;
        return host.matches('main, .app-main, #content-container, .content, #content');
    }

    function setAiosHostMode(enabled) {
        if (!aiosScope) return;
        const host = aiosScope.parentElement;
        aiosScope.classList.toggle('aios-p-scope-active', enabled);

        if (!shouldHideHostSiblings(host)) return;
        Array.from(host.children).forEach(child => {
            if (child === aiosScope) return;

            if (enabled) {
                if (child.dataset.aiosHiddenByPlugin !== 'true') {
                    child.dataset.aiosHiddenByPlugin = 'true';
                    child.dataset.aiosPreviousDisplay = child.style.display || '';
                }
                child.style.display = 'none';
                return;
            }

            if (child.dataset.aiosHiddenByPlugin === 'true') {
                child.style.display = child.dataset.aiosPreviousDisplay || '';
                delete child.dataset.aiosHiddenByPlugin;
                delete child.dataset.aiosPreviousDisplay;
            }
        });
    }

    function hideAiosSections() {
        currentAiosSection = null;
        AIOS_SECTIONS.forEach(sid => {
            const el = document.getElementById('section-' + sid);
            if (el) el.classList.remove('active');
        });
        document.querySelectorAll('[id^="nav-aios-"][data-nav-target]').forEach(el => {
            el.classList.remove('active');
            el.classList.remove('aios-p-nav-active');
        });
        setAiosHostMode(false);
    }

    function showSection(id) {
        if (!AIOS_SECTIONS.includes(id)) return;
        currentAiosSection = id;
        setAiosHostMode(true);
        hideNativeSections();
        AIOS_SECTIONS.forEach(sid => {
            const el = document.getElementById('section-' + sid);
            if (el) {
                el.classList.toggle('active', sid === id);
            }
        });

        document.querySelectorAll('[id^="nav-aios-"][data-nav-target]').forEach(el => {
            const active = el.getAttribute('data-nav-target') === id;
            el.classList.toggle('active', active);
            el.classList.toggle('aios-p-nav-active', active);
        });
    }

    const MENU_ITEMS = [
        { id: 'nav-aios-gpu', target: 'aios-gpu', icon: 'fa-microchip', text: 'GPU 监控' },
        { id: 'nav-aios-model', target: 'aios-model', icon: 'fa-cube', text: '模型管理' },
    ];

    function ensureAiosMenus(nav) {
        if (!nav) return;

        document.querySelectorAll('[id^="nav-aios-"][data-nav-target]').forEach(el => {
            if (!nav.contains(el)) {
                const group = el.closest('#aios-p-nav-group');
                if (group) group.remove();
                else el.remove();
            }
        });

        const hasAllMenus = MENU_ITEMS.every(item => nav.querySelector('#' + item.id));
        if (hasAllMenus) return;

        nav.querySelector('#aios-p-nav-group')?.remove();
        nav.querySelectorAll('[id^="nav-aios-"][data-nav-target], .aios-p-nav-divider').forEach(el => el.remove());

        const isAiclientNav = nav.classList.contains('sidebar-nav');
        const isVueNav = nav.classList.contains('nav-container') || !!nav.querySelector('.nav-group, .group-items');
        const itemClass = isAiclientNav ? 'nav-item aios-p-nav-item' : 'aios-p-nav-item';
        const menuHTML = MENU_ITEMS.map(item =>
            `<a href="#${item.target}" class="${itemClass}" id="${item.id}" data-nav-target="${item.target}" aria-label="${item.text}"><i class="fas ${item.icon}" aria-hidden="true"></i><span class="aios-p-nav-label">${item.text}</span></a>`
        ).join('');

        const fullMenuHTML = isVueNav
            ? `<div class="aios-p-nav-group" id="aios-p-nav-group"><h3 class="aios-p-nav-title">AI 管控</h3><div class="aios-p-nav-items">${menuHTML}</div></div>`
            : (isAiclientNav ? menuHTML : '<div class="aios-p-nav-divider"></div>' + menuHTML);

        const existingDivider = nav.querySelector('.aios-p-nav-divider, .nav-divider');
        if (existingDivider) {
            existingDivider.insertAdjacentHTML('afterend', fullMenuHTML);
        } else {
            nav.insertAdjacentHTML('beforeend', fullMenuHTML);
        }
    }

    function ensureAiosScope(content) {
        if (document.getElementById('section-aios-gpu')) return;

        if (aiosScope && aiosScope.parentNode) {
            aiosScope.remove();
        }
        aiosScope = document.createElement('div');
        aiosScope.className = 'aios-p-scope';
        aiosScope.innerHTML = GPU_HTML + MODEL_HTML;
        content.appendChild(aiosScope);
    }

    function injectUI(nav, content) {
        if (!document.querySelector('link[href="/plugins/ai-os-manager/styles.css"]')) {
            document.head.insertAdjacentHTML('beforeend', CSS_LINK);
        }
        if (!document.getElementById('aios-toast-container')) {
            document.body.insertAdjacentHTML('beforeend', TOAST_CONTAINER);
        }

        ensureAiosScope(content);
        ensureAiosMenus(nav);

        if (!initialized) {
            setupGlobalEventHandlers();
            setupHostNavigationGuard();
            initialized = true;
        }

        const initialSection = getInitialAiosSection();
        if (initialSection) {
            showSection(initialSection);
        } else {
            hideAiosSections();
        }
    }

    function startMenuWatcher(nav, content) {
        const watcher = new MutationObserver(() => {
            ensureAiosMenus(nav);
            ensureAiosScope(content);
        });
        watcher.observe(nav, { childList: true, subtree: true });
        watcher.observe(content, { childList: true, subtree: true });
    }

    let currentAiosSection = null;
    function setupHostNavigationGuard() {
        const guard = new MutationObserver((mutations) => {
            for (const mutation of mutations) {
                if (mutation.type !== 'attributes' || mutation.attributeName !== 'class') continue;
                const target = mutation.target;
                if (!target.id || !target.id.startsWith('section-aios-')) continue;
                const wasActive = target.classList.contains('active');
                if (currentAiosSection && !wasActive && currentAiosSection === target.id.replace('section-', '')) {
                    setTimeout(() => target.classList.add('active'), 0);
                }
            }
        });
        if (aiosScope) {
            guard.observe(aiosScope, { attributes: true, subtree: true, attributeFilter: ['class'] });
        }
    }

    function handleActionClick(action, target) {
        switch(action) {
            case 'gpu-refresh':
                window.AiosManager.gpu.refresh();
                break;
            case 'model-refresh':
                window.AiosManager.model.refresh();
                break;
            case 'health-refresh':
                window.AiosManager.health.refresh();
                break;
            case 'ratelimit-refresh':
                window.AiosManager.ratelimit.refresh();
                break;
            case 'config-refresh':
                window.AiosManager.config.refresh();
                break;
            case 'switch-model':
                window.AiosManager.model.switchModel();
                break;
            case 'download-model':
                window.AiosManager.model.download();
                break;
            case 'switch-engine':
                const engine = target.getAttribute('data-engine');
                if (engine) window.AiosManager.gpu.switchEngine(engine);
                break;
            case 'download-by-name':
                const modelName = target.getAttribute('data-model');
                window.AiosManager.model.downloadByName(modelName);
                break;
            case 'cancel-switch':
                window.AiosManager.model.cancelSwitch();
                break;
            case 'start-model':
                window.AiosManager.model.start(target.getAttribute('data-model'));
                break;
            case 'switch-to-model':
                window.AiosManager.model.switchTo(target.getAttribute('data-model'), target.getAttribute('data-engine'));
                break;
            case 'stop-model':
                window.AiosManager.model.stop(target.getAttribute('data-model'));
                break;
            case 'cancel-download':
                const cancelTaskId = target.getAttribute('data-task-id');
                window.AiosManager.model.cancelDownload(cancelTaskId);
                break;
            case 'retry-download':
                const retryTaskId = target.getAttribute('data-task-id');
                window.AiosManager.model.retryDownload(retryTaskId);
                break;
            case 'ratelimit-save':
                window.AiosManager.ratelimit.save();
                break;
            case 'config-save':
                window.AiosManager.config.save();
        }
    }

    function updateAiosHash(target) {
        if (!AIOS_SECTIONS.includes(target)) return;
        const nextUrl = window.location.pathname + window.location.search + '#' + target;
        if (window.location.hash.slice(1) === target) return;
        if (window.history && window.history.pushState) {
            window.history.pushState({ aiosSection: target }, '', nextUrl);
        } else {
            window.location.hash = target;
        }
    }

    function clearAiosHash() {
        if (!AIOS_SECTIONS.includes(window.location.hash.slice(1))) return;
        const nextUrl = window.location.pathname + window.location.search;
        if (window.history && window.history.replaceState) {
            window.history.replaceState({}, '', nextUrl);
        } else {
            window.location.hash = '';
        }
    }

    function setupGlobalEventHandlers() {
        document.addEventListener('click', function(e) {
            const navItem = e.target.closest('[data-nav-target]');
            if (navItem) {
                const navId = navItem.getAttribute('id');
                if (navId && navId.startsWith('nav-aios-')) {
                    e.preventDefault();
                    e.stopPropagation();
                    const target = navItem.getAttribute('data-nav-target');
                    if (target) {
                        showSection(target);
                        updateAiosHash(target);
                        if (window.AiosManager && window.AiosManager[target.replace('aios-', '')]) {
                            window.AiosManager[target.replace('aios-', '')].refresh();
                        }
                    }
                }
                return;
            }

            const nativeNavItem = e.target.closest('.nav-item[data-section], button.nav-item, a.nav-item');
            if (nativeNavItem) {
                hideAiosSections();
                clearAiosHash();
            }

            const actionBtn = e.target.closest('[data-action]');
            if (actionBtn) {
                if (actionBtn.disabled || actionBtn.getAttribute('aria-disabled') === 'true') return;
                e.preventDefault();
                const action = actionBtn.getAttribute('data-action');
                handleActionClick(action, actionBtn);
            }
        });

        const handleRouteChange = () => {
            const hash = window.location.hash.slice(1);
            const isAiosSection = AIOS_SECTIONS.includes(hash);
            if (isAiosSection) {
                showSection(hash);
            } else {
                hideAiosSections();
            }
        };

        window.addEventListener('hashchange', handleRouteChange);
        window.addEventListener('popstate', handleRouteChange);
        
        if (window.history && window.history.pushState) {
            const originalPushState = window.history.pushState;
            const originalReplaceState = window.history.replaceState;
            
            window.history.pushState = function() {
                originalPushState.apply(this, arguments);
                handleRouteChange();
            };
            
            window.history.replaceState = function() {
                originalReplaceState.apply(this, arguments);
                handleRouteChange();
            };
        }
    }

    window.AiosManager = {
        gpu: {
            currentRange: 'min',
            lastEngineData: null,
            engineConfigSnapshot: null,
            historyPanel: null,
            historyPanelLimits: {
                min: 60,
                hour: 120,
                day: 240,
            },
            refreshState: {
                loading: false,
                lastUpdated: '',
                lastError: ''
            },
            switchingEngine: '',
            pendingTargetEngine: '',
            _engineSwitchPollTimer: null,
            _engineSwitchStableCount: 0,
            _engineSwitchDeadlineAt: 0,
            _engineSwitchTargetModel: '',
            _engineSwitchTargetEngine: '',
            _engineSwitchTargetPort: null,
            _engineSwitchTargetSessionId: '',
            _engineSwitchStableThreshold: 2,
            _engineSwitchPollInterval: 2000,
            _engineSwitchTimeoutMs: 120000,
            _engineSwitchDefaultPorts: {
                vllm: 8000,
                sglang: 8100,
                llamacpp: 8200,
            },
            normalizeHistoryRange(range) {
                const value = String(range || 'min').toLowerCase();
                if (['min', 'minute', 'minutes', '1m', 'm'].includes(value)) return 'min';
                if (['hour', 'hours', 'h', 'hr'].includes(value)) return 'hour';
                if (['day', 'days', 'd'].includes(value)) return 'day';
                return 'min';
            },
            normalizeModelName(value) {
                const raw = String(value || '').trim();
                if (!raw) return '';
                const clean = raw.split('/').filter(Boolean).pop();
                return clean ? clean.toLowerCase() : '';
            },
            getHistoryLimit(range) {
                return this.historyPanelLimits[this.normalizeHistoryRange(range)] || this.historyPanelLimits.min;
            },
            ensureHistoryPanel() {
                const container = document.getElementById('aios-gpu-history');
                if (!container) return false;
                if (this.historyPanel) return true;
                if (!window.AiosGPUCharts || typeof window.AiosGPUCharts.createDashboard !== 'function') {
                    container.innerHTML = errorHTML('GPU 图表组件未加载，请刷新后重试');
                    return false;
                }
                this.historyPanel = window.AiosGPUCharts.createDashboard('aios-gpu-history', {
                    limit: this.historyPanelLimits
                });
                return true;
            },
            async refreshHistoryData() {
                if (!this.ensureHistoryPanel()) return;
                const range = this.normalizeHistoryRange(this.currentRange);
                const count = this.getHistoryLimit(range);
                const query = new URLSearchParams({ time_range: range, count: String(count) }).toString();
                const result = await adminFetch(`/api/gpu-monitor/history?${query}`);
                const payload = result?.history || result?.data || result;
                if (Array.isArray(payload)) {
                    this.historyPanel.setRange(range);
                    this.historyPanel.update(payload, { range, summary: result });
                    return;
                }
                if (window.AiosGPUCharts && typeof window.AiosGPUCharts.renderGpuHistoryMissing === 'function') {
                    window.AiosGPUCharts.renderGpuHistoryMissing('aios-gpu-history', range);
                    return;
                }
                const container = document.getElementById('aios-gpu-history');
                if (container) container.innerHTML = emptyHTML('暂无历史数据');
            },
            clearEngineSwitchPolling() {
                if (this._engineSwitchPollTimer) {
                    clearTimeout(this._engineSwitchPollTimer);
                    this._engineSwitchPollTimer = null;
                }
                this._engineSwitchStableCount = 0;
                this._engineSwitchDeadlineAt = 0;
                this._engineSwitchTargetModel = '';
                this._engineSwitchTargetPort = null;
                this._engineSwitchTargetEngine = '';
                this._engineSwitchTargetSessionId = '';
            },
            isTerminalEnginePhase(phase) {
                const normalized = String(phase || '').toLowerCase();
                return new Set(['completed', 'failed', 'rolled_back']).has(normalized);
            },
            getEngineSessionState(session) {
                if (!session) return { active: false, terminal: false, phase: '', completed: false, error: '', rollbackReason: '' };
                const phase = String(session.overall_phase || '').toLowerCase();
                const terminal = this.isTerminalEnginePhase(phase);
                return {
                    active: !terminal && !session.error && !session.rollback_reason && !session.completed_successfully,
                    terminal,
                    phase,
                    completed: !!session.completed_successfully,
                    error: session.error || '',
                    rollbackReason: session.rollback_reason || ''
                };
            },
            getRunningServices(payload) {
                const data = payload || {};
                if (Array.isArray(data.services)) return data.services;
                if (Array.isArray(data.current?.services)) return data.current.services;
                if (Array.isArray(data.engines)) return data.engines;
                if (Array.isArray(data.current?.engines)) return data.current.engines;
                return [];
            },
            getEngineRegistry(payload) {
                const scheduler = payload?.scheduler_status || payload?.current?.scheduler_status || null;
                if (!scheduler || typeof scheduler !== 'object') return {};
                const registry = scheduler.engine_registry;
                return registry && typeof registry === 'object' ? registry : {};
            },
            setEngineConfigSnapshot(payload = {}) {
                if (!payload) {
                    this.engineConfigSnapshot = null;
                    return;
                }
                const raw = payload.data || payload || {};
                this.engineConfigSnapshot = raw;
            },
            getEngineConfig(type, payload = this.engineConfigSnapshot) {
                const normalized = normalizeEngineType(type);
                const source = payload || {};
                if (!source || typeof source !== 'object') return {};
                const direct = source[normalized] || source[normalized + '_config'] || source[normalized.toUpperCase()] || {};
                const nested = source.config?.[normalized] || source.configs?.[normalized] || {};
                const enginesRoot = source.engines || source.engine_config || source.engineConfigs || {};
                const fromEngines = enginesRoot?.[normalized] || {};
                const merged = { ...(typeof direct === 'object' && direct ? direct : {}), ...(typeof nested === 'object' && nested ? nested : {}), ...(typeof fromEngines === 'object' && fromEngines ? fromEngines : {}) };
                return merged;
            },
            isEngineEnabled(type, payload = this.engineConfigSnapshot) {
                if (normalizeEngineType(type) === 'vllm') return true;
                const source = payload || {};
                const hasConfigPayload = !!(source && typeof source === 'object' && Object.keys(source).length > 0);
                const config = this.getEngineConfig(type, payload);
                if (!config || typeof config !== 'object' || Object.keys(config).length === 0) {
                    return !hasConfigPayload;
                }
                if (!Object.prototype.hasOwnProperty.call(config, 'enabled')) return true;
                return config.enabled !== false;
            },
            getEngineConfiguredPort(type, payload = this.engineConfigSnapshot) {
                const config = this.getEngineConfig(type, payload);
                if (!config || typeof config !== 'object') return null;
                return parsePortValue(config.port || config.http_port || config.bind_port || config.api_port || config.listen_port || config.host_port);
            },
            getEngineRunningPort(type, payload = this.lastEngineData) {
                const services = this.getRunningServices(payload || {});
                const target = services.find((s) => normalizeEngineType(s?.engine_type || s?.engine || s?.name || s?.type) === normalizeEngineType(type));
                return parsePortValue(target?.port);
            },
            getEngineDefaultPort(type, payload = this.lastEngineData, configPayload = this.engineConfigSnapshot) {
                return this.getEngineRunningPort(type, payload)
                    || this.getEngineConfiguredPort(type, configPayload)
                    || 8000;
            },
            getEngineConfigEnabledMap(payload = this.engineConfigSnapshot) {
                const map = {
                    vllm: this.isEngineEnabled('vllm', payload),
                    sglang: this.isEngineEnabled('sglang', payload),
                    llamacpp: this.isEngineEnabled('llamacpp', payload),
                };
                return map;
            },
            isEngineSwitchServiceMatch(service, targetEngine, targetModel, targetPort) {
                const serviceEngine = normalizeEngineType(service?.engine_type || service?.engine || service?.name || '');
                if (serviceEngine !== targetEngine) return false;
                if (targetPort != null && !Number.isNaN(Number(targetPort)) && Number(service?.port) !== Number(targetPort)) {
                    return false;
                }
                if (!targetModel) return true;
                const serviceModel = this.normalizeModelName(service?.model_name || service?.model || '');
                const expectedModel = this.normalizeModelName(targetModel);
                if (!serviceModel || !expectedModel) return serviceEngine === targetEngine;
                return serviceModel === expectedModel;
            },
            refreshStatus(summary = {}) {
                this.refreshState = {
                    ...this.refreshState,
                    ...summary,
                    lastUpdated: summary.lastUpdated || new Date().toLocaleTimeString('zh-CN', { hour12: false })
                };
                this.renderSummary();
            },
            renderSummary() {
                const { loading, lastUpdated, lastError } = this.refreshState;
                if (window.AiosGPUCharts && typeof window.AiosGPUCharts.renderSummaryCard === 'function') {
                    window.AiosGPUCharts.renderSummaryCard('aios-gpu-summary', {
                        loading,
                        lastUpdated: lastUpdated || '-',
                        lastError: lastError || '',
                    });
                    return;
                }
                const el = document.getElementById('aios-gpu-summary');
                if (!el) return;
                el.innerHTML = `<div class="aios-p-summary-card ${loading ? 'is-loading' : ''}">
                    <div class="aios-p-summary-main">
                        <div class="aios-p-summary-title"><i class="fas fa-wave-square"></i> 监控状态</div>
                        <div class="aios-p-summary-meta">${loading ? '正在刷新 GPU / 引擎状态…' : '数据刷新正常'}</div>
                    </div>
                    <div class="aios-p-summary-side">
                        <span class="aios-p-summary-pill ${lastError ? 'is-error' : ''}">${lastError ? `异常: ${escapeHtml(lastError)}` : `最近更新 ${escapeHtml(lastUpdated || '-')}`}</span>
                    </div>
                </div>`;
            },
            async refresh(showLoading = true) {
                if (showLoading) this.refreshStatus({ loading: true, lastError: '' });
                let historyError = '';
                try {
                    const [gpuData, engineData] = await Promise.all([
                        adminFetch('/api/gpu-monitor/info'),
                        adminFetch('/api/engine/status')
                    ]);
                    this.renderGPUCards(gpuData);
                    this.renderEngineStatus(engineData);
                    try {
                        await this.refreshHistoryData();
                    } catch (e) {
                        historyError = e.message;
                    }
                    this.loadEngineConfig(false);
                    this.refreshState = {
                        ...this.refreshState,
                        loading: false,
                        lastError: historyError,
                        lastUpdated: new Date().toLocaleTimeString('zh-CN', { hour12: false })
                    };
                    this.renderGPUCards(gpuData);
                    if (historyError) showToast(`GPU 历史图更新失败: ${historyError}`, 'warning');
                } catch (e) {
                    const el = document.getElementById('aios-gpu-stats');
                    if (el) el.innerHTML = errorHTML(e.message);
                    this.refreshStatus({ loading: false, lastError: e.message });
                }
            },
            renderGPUCards(data) {
                const gpuDataArr = data?.data || [];
                const gpu = Array.isArray(gpuDataArr) ? gpuDataArr[0] : null;
                if (!window.AiosGPUCharts || typeof window.AiosGPUCharts.renderGPUCards !== 'function') {
                    const summaryEl = document.getElementById('aios-gpu-summary');
                    const el = document.getElementById('aios-gpu-stats');
                    if (!gpu) {
                        if (summaryEl) summaryEl.innerHTML = emptyHTML('未检测到 GPU');
                        if (el) el.innerHTML = emptyHTML('未检测到 GPU');
                        return;
                    }
                    const util = Number(gpu.gpuUtilization ?? 0);
                    const memUsed = Number(gpu.memoryUsed ?? 0);
                    const memTotal = Number(gpu.memoryTotal ?? 0);
                    const memPct = memTotal > 0 ? (memUsed / memTotal * 100) : 0;
                    const temp = Number(gpu.temperature ?? 0);
                    const power = Number(gpu.powerDraw ?? 0);
                    if (summaryEl) {
                        summaryEl.innerHTML = `<div class="aios-p-summary-grid">
                            <div class="aios-p-summary-card"><div class="aios-p-summary-title"><i class="fas fa-tag"></i> 设备</div><div class="aios-p-summary-value">${escapeHtml(gpu.name || '-')}</div><div class="aios-p-summary-meta">驱动 ${escapeHtml(String(gpu.driverVersion || gpu.driver_version || '-'))}</div></div>
                            <div class="aios-p-summary-card"><div class="aios-p-summary-title"><i class="fas fa-gauge-high"></i> 负载概览</div><div class="aios-p-summary-value">${util.toFixed(1)}% / ${memPct.toFixed(1)}%</div><div class="aios-p-summary-meta">利用率 / 显存占用</div></div>
                            <div class="aios-p-summary-card"><div class="aios-p-summary-title"><i class="fas fa-clock"></i> 刷新时间</div><div class="aios-p-summary-value">${escapeHtml(this.refreshState.lastUpdated || '-')}</div><div class="aios-p-summary-meta">${this.refreshState.lastError ? `异常: ${escapeHtml(this.refreshState.lastError)}` : '采样正常'}</div></div>
                        </div>`;
                    }
                    const cards = [
                        { icon: 'fa-chart-line', label: '利用率', value: `${util}%`, progress: util, ptype: util > 80 ? 'danger' : util > 50 ? 'warning' : 'success' },
                        { icon: 'fa-memory', label: '显存', value: `${formatBytes(memUsed)} / ${formatBytes(memTotal)}`, progress: memPct, ptype: memPct > 80 ? 'danger' : memPct > 50 ? 'warning' : 'success' },
                        { icon: 'fa-thermometer-half', label: '温度', value: `${temp}°C`, progress: temp, ptype: temp > 80 ? 'danger' : temp > 60 ? 'warning' : 'success' },
                        { icon: 'fa-plug', label: '功耗', value: `${power}W` },
                    ];
                    if (el) {
                        el.innerHTML = cards.map(c => {
                            const prog = c.progress != null ? `<div class="aios-p-progress-bar"><div class="aios-p-progress-fill aios-${c.ptype}" style="width:${Math.min(c.progress, 100)}%"></div></div>` : '';
                            return `<div class="aios-p-stat-card"><div class="aios-p-stat-icon"><i class="fas ${c.icon}"></i></div><div class="aios-p-stat-body"><div class="aios-p-stat-label">${c.label}</div><div class="aios-p-stat-value">${c.value}</div>${prog}</div></div>`;
                        }).join('');
                    }
                    return;
                }
                const refreshMeta = {
                    loading: this.refreshState.loading,
                    lastUpdated: this.refreshState.lastUpdated || '-',
                    lastError: this.refreshState.lastError || '',
                };
                if (!gpu) {
                    const summaryEl = document.getElementById('aios-gpu-summary');
                    if (summaryEl) summaryEl.innerHTML = emptyHTML('未检测到 GPU');
                }
                window.AiosGPUCharts.renderGPUCards('aios-gpu-stats', gpu, refreshMeta);
            },
            renderEngineStatus(data) {
                const result = data.data || data || {};
                const raw = result.current || result || {};
                this.lastEngineData = raw;
                const services = Array.isArray(raw.services) ? raw.services : (Array.isArray(raw.engines) ? raw.engines : []);
                const runningServices = services.filter(s => s?.status === 'running');
                const detectedCurrentEngine = normalizeEngineType(
                    runningServices[0]?.engine_type
                        || runningServices[0]?.engine
                        || raw.current_engine
                        || result.current_engine
                        || this.currentEngine
                        || ''
                );
                this.currentEngine = detectedCurrentEngine;
                const engineTypes = ['vllm', 'sglang', 'llamacpp'];
                const switchSession = result.switch_session || raw.switch_session || result.session || raw.session || null;
                const sessionState = this.getEngineSessionState(switchSession);
                const rawCurrentEngine = detectedCurrentEngine;
                const switchingFromBackend = !!(raw.switching || result.switching || sessionState.active);
                const isSwitching = !!(switchingFromBackend || this.switchingEngine || this._engineSwitchPollTimer);
                const switchingTarget = normalizeEngineType(
                    this.switchingEngine
                        || this.pendingTargetEngine
                        || this._engineSwitchTargetEngine
                        || (switchSession && (switchSession.target_engine || switchSession.engine_type))
                        || rawCurrentEngine
                        || ''
                );
                if (!isSwitching && !sessionState.active) {
                    this.switchingEngine = '';
                    this.pendingTargetEngine = '';
                    this._engineSwitchTargetEngine = '';
                }
                const globalActionDisabled = isSwitching;
                const configEditor = document.getElementById('aios-engine-config-editor');
                let editorConfig = {};
                if (configEditor?.value) {
                    try {
                        editorConfig = JSON.parse(configEditor.value);
                    } catch {}
                }
                const config = Object.keys(this.engineConfigSnapshot || {}).length > 0
                    ? this.engineConfigSnapshot
                    : editorConfig;
                const configRoot = config.config || config.current || config;
                const configMap = {
                    vllm: configRoot.vllm || configRoot.vllm_config || {},
                    sglang: configRoot.sglang || configRoot.sglang_config || {},
                    llamacpp: configRoot.llamacpp || configRoot.llama_cpp || configRoot.llamacpp_config || configRoot.llama_cpp_config || {},
                };
                const enabledMap = this.getEngineConfigEnabledMap(config);
                const engines = engineTypes.map(type => {
                    const svc = services.find(s => normalizeEngineType(s.engine_type || s.name || s.type) === type) || null;
                    const cfg = configMap[type] || {};
                    const hasConfig = type === 'vllm' || Object.keys(cfg).length > 0;
                    const engineEnabled = enabledMap[type] !== false;
                    const status = !engineEnabled && hasConfig ? 'disabled' : (svc?.status || (svc ? 'stopped' : 'not_found'));
                    const running = status === 'running' && engineEnabled;
                    const model = svc?.model || svc?.model_name || cfg.model_name || cfg.model || '-';
                    const port = svc?.port ?? cfg.port ?? cfg.http_port ?? '-';
                    const uptime = svc?.uptime_seconds ? `${Math.floor(svc.uptime_seconds / 3600)}h${Math.floor((svc.uptime_seconds % 3600) / 60)}m` : '-';
                    const pid = svc?.pid ?? null;
                    const health = svc?.health || cfg.health_check || '-';
                    const host = svc?.host || cfg.host || cfg.bind_host || '-';
                    const parallel = cfg.tensor_parallel_size ?? cfg.tp ?? cfg.parallel_size ?? '-';
                    const gpuMem = cfg.gpu_memory_utilization ?? cfg.mem_fraction_static ?? cfg.gpu_memory_fraction ?? '-';
                    const extras = [
                        cfg.max_model_len != null ? `上下文 ${cfg.max_model_len}` : '',
                        cfg.quantization ? `量化 ${cfg.quantization}` : '',
                        cfg.dtype ? `精度 ${cfg.dtype}` : '',
                    ].filter(Boolean);
                    return { type, status, running, model, port, uptime, pid, health, host, parallel, gpuMem, extras };
                });
                const html = `<div class="aios-p-engine-grid">${engines.map(e => {
                    const unavailable = e.status === 'not_found';
                    const isPending = this.switchingEngine === e.type || (isSwitching && switchingTarget === e.type);
                    const isDisabled = e.status === 'disabled';
                    const canSwitch = !globalActionDisabled && !unavailable && !isDisabled && !e.running;
                    const actionAttrs = canSwitch ? `data-action="switch-engine" data-engine="${e.type}"` : 'disabled aria-disabled="true"';
                    const actionIcon = e.running ? 'fa-check-circle' : (isDisabled ? 'fa-ban' : (unavailable ? 'fa-triangle-exclamation' : isPending ? 'fa-spinner fa-spin' : 'fa-play'));
                    const actionText = e.running ? '当前引擎' : (isDisabled ? '已禁用' : (unavailable ? '未配置' : isPending ? '切换中...' : '切换到此引擎'));
                    const statusText = e.running
                        ? '运行中'
                        : isDisabled ? '已禁用'
                        : (isPending ? `切换中 (${switchingTarget ? engineDisplayName(switchingTarget) : '待确认'})` : (e.status === 'not_found' ? '未配置/未安装' : '已停止'));
                    const cardClass = `${e.running ? 'aios-p-engine-running' : 'aios-p-engine-stopped'} ${isPending ? 'aios-p-engine-pending' : ''} ${isDisabled ? 'aios-p-engine-disabled' : ''}`;
                    return `
                    <div class="aios-p-engine-card ${cardClass}" data-engine-type="${e.type}">
                        <div class="aios-p-engine-header">
                            <div class="aios-p-engine-icon"><i class="fas fa-bolt"></i></div>
                            <div class="aios-p-engine-title-row">
                                <div class="aios-p-engine-title">${engineDisplayName(e.type)}</div>
                                <div class="aios-p-engine-status-text ${e.running ? 'aios-p-engine-running-text' : 'aios-p-engine-stopped-text'}">${statusText}</div>
                            </div>
                        </div>
                        <div class="aios-p-engine-info-grid">
                            <div class="aios-p-engine-info-item aios-p-engine-info-wide"><span>模型</span><strong>${e.model}</strong></div>
                            <div class="aios-p-engine-info-item"><span>端口</span><strong>${e.port}</strong></div>
                            <div class="aios-p-engine-info-item"><span>主机</span><strong>${e.host}</strong></div>
                            <div class="aios-p-engine-info-item"><span>并行</span><strong>${e.parallel}</strong></div>
                            <div class="aios-p-engine-info-item"><span>显存阈值</span><strong>${e.gpuMem}</strong></div>
                            <div class="aios-p-engine-info-item"><span>健康</span><strong>${e.health}</strong></div>
                            <div class="aios-p-engine-info-item"><span>运行</span><strong>${e.uptime}</strong></div>
                            <div class="aios-p-engine-info-item"><span>PID</span><strong>${e.pid ?? '-'}</strong></div>
                        </div>
                        ${e.extras.length ? `<div class="aios-p-engine-tags">${e.extras.map(tag => `<span class="aios-p-engine-tag">${tag}</span>`).join('')}</div>` : ''}
                        <div class="aios-p-engine-actions">
                            <button class="aios-p-btn aios-p-btn-sm ${e.running ? 'aios-p-btn-success' : ''}" style="width:100%;" ${actionAttrs}>
                                <i class="fas ${actionIcon}"></i> ${actionText}
                            </button>
                        </div>
                    </div>`;
                }).join('')}</div>`;
                const el = document.getElementById('aios-engine-status');
                if (el) el.innerHTML = html;
            },
            async switchEngine(engineType) {
                const targetEngine = normalizeEngineType(engineType);
                try {
                    if (this.switchingEngine) {
                        showToast('已有引擎切换进行中，请稍候', 'warning');
                        return;
                    }
                    if (!this.isEngineEnabled(targetEngine)) {
                        showToast(`${engineDisplayName(targetEngine)} 当前已禁用，请先在引擎配置中启用`, 'warning');
                        return;
                    }
                    let modelName = '';
                    const aggResult = await adminFetch('/api/model-switch/aggregated');
                    const aggData = aggResult.data || aggResult;
                    const groups = aggData.groups || [];
                    const runningServices = this.getRunningServices(this.lastEngineData || {});
                    const currentService = runningServices.find(s => normalizeEngineType(s.engine_type || s.engine || s.name || s.type) === normalizeEngineType(this.currentEngine || this.pendingTargetEngine || ''))
                        || runningServices.find(s => s.status === 'running');
                    modelName = currentService?.model_name || currentService?.model || '';
                    for (const g of groups) {
                        for (const v of (g.variants || [])) {
                            if (modelName) break;
                            if (v.running || v.is_current) { modelName = v.name || g.base_name; break; }
                        }
                        if (modelName) break;
                    }
                    if (!modelName && groups.length > 0) modelName = groups[0].base_name;
                    if (!modelName) { showToast('没有可用模型，请先下载模型', 'warning'); return; }
                    const confirmed = await showConfirm(`确认切换引擎到 ${engineDisplayName(targetEngine)}？该操作会重启当前推理服务。`);
                    if (!confirmed) return;
                    this.switchingEngine = targetEngine;
                    this.pendingTargetEngine = targetEngine;
                    this.renderEngineStatus({ data: { current: this.lastEngineData || {} } });
                    showToast(`正在切换到 ${engineDisplayName(targetEngine)}，请等待状态稳定`, 'info');
                    const requestBody = { model_name: modelName, engine_type: targetEngine };
                    const targetPort = parsePortValue(this._engineSwitchTargetPort || this.getEngineDefaultPort(targetEngine) || this._engineSwitchDefaultPorts[targetEngine] || null);
                    if (targetPort != null) {
                        requestBody.port = targetPort;
                    }
                    this._engineSwitchTargetEngine = targetEngine;
                    this._engineSwitchTargetModel = this.normalizeModelName(modelName);
                    this._engineSwitchTargetPort = targetPort;
                    this._engineSwitchDeadlineAt = Date.now() + this._engineSwitchTimeoutMs;
                    const result = await adminFetch('/api/engine/switch', {
                        method: 'POST',
                        body: JSON.stringify(requestBody)
                    });
                    if (result.success || result.data?.success) {
                        const sessionId = result.data?.session_id || result.session_id || '';
                        const reason = result.data?.reason || result.reason || '';
                        this._engineSwitchTargetSessionId = sessionId;
                        this._engineSwitchTargetModel = this.normalizeModelName(modelName);
                        this._engineSwitchTargetEngine = targetEngine;
                        this._engineSwitchTargetPort = targetPort;
                        this._engineSwitchStableCount = 0;
                        this._engineSwitchDeadlineAt = Date.now() + this._engineSwitchTimeoutMs;
                        this.pollEngineSwitchStatus(targetEngine, modelName);
                        this.renderEngineStatus({ data: { current: this.lastEngineData || {}, switching: true, switch_session: result.session || result.data?.session || null } });
                        showToast(`切换请求已提交：${engineDisplayName(targetEngine)}，正在确认`, 'success');
                        this.refresh(false);
                        if (reason === 'already_running_same_engine') {
                            this.clearEngineSwitchPolling();
                            this.switchingEngine = '';
                            this.pendingTargetEngine = '';
                            this._engineSwitchTargetEngine = '';
                            this._engineSwitchTargetSessionId = '';
                        }
                    } else {
                        const reason = result.data?.reason || result.reason || result.error || '未知错误';
                        if (reason === 'insufficient_gpu_memory') {
                            showToast(`GPU显存不足: ${result.suggestion || ''}`, 'error');
                        } else if (reason === 'already_running_same_engine') {
                            showToast(`${engineDisplayName(targetEngine)} 已是当前引擎`, 'info');
                            this.clearEngineSwitchPolling();
                            this.switchingEngine = '';
                            this.pendingTargetEngine = '';
                        } else {
                            showToast(`切换引擎失败: ${reason}`, 'error');
                            this.clearEngineSwitchPolling();
                            this.switchingEngine = '';
                            this.pendingTargetEngine = '';
                        }
                    }
                } catch (e) {
                    showToast(`切换引擎失败: ${e.message}`, 'error');
                    this.clearEngineSwitchPolling();
                    this.switchingEngine = '';
                    this.pendingTargetEngine = '';
                } finally {
                    if (!this._engineSwitchPollTimer) {
                        this.refresh(false);
                    }
                }
            },
            pollEngineSwitchStatus(targetEngine, targetModel) {
                if (this._engineSwitchPollTimer) {
                    clearTimeout(this._engineSwitchPollTimer);
                    this._engineSwitchPollTimer = null;
                }
                const normalizedTarget = normalizeEngineType(targetEngine);
                const normalizedModel = this.normalizeModelName(targetModel || this._engineSwitchTargetModel || '');
                const deadline = this._engineSwitchDeadlineAt || (Date.now() + this._engineSwitchTimeoutMs);
                this._engineSwitchDeadlineAt = deadline;
                this._engineSwitchStableCount = 0;

                const finish = (toastType, message, refreshModel = false) => {
                    this.clearEngineSwitchPolling();
                    this.switchingEngine = '';
                    this.pendingTargetEngine = '';
                    this._engineSwitchTargetEngine = '';
                    if (message) showToast(message, toastType);
                    this.refresh(false);
                    if (refreshModel) window.AiosManager.model.refresh();
                };

                const loop = async () => {
                    if (!normalizedTarget) {
                        finish('warning', '');
                        return;
                    }
                    if (Date.now() >= deadline) {
                        finish('warning', `引擎切换超时：${engineDisplayName(normalizedTarget)}，请检查实际运行状态`);
                        return;
                    }
                    try {
                        const status = await adminFetch('/api/engine/status');
                        this.renderEngineStatus(status);
                        const payload = status.data || status || {};
                        const raw = payload.current || payload;
                        const services = this.getRunningServices(payload);
                        const matchingServices = services.filter(
                            s => normalizeEngineType(s.engine_type || s.engine || s.name || s.type) === normalizedTarget && s.status === 'running'
                        );
                        const runningService = matchingServices.find(s => this.isEngineSwitchServiceMatch(s, normalizedTarget, normalizedModel, this._engineSwitchTargetPort)) || matchingServices[0] || null;
                        const session = payload.switch_session || raw.switch_session || payload.session || raw.session || null;
                        const sessionState = this.getEngineSessionState(session);
                        const currentEngine = normalizeEngineType(
                            runningService?.engine_type
                                || runningService?.engine
                                || payload.current_engine
                                || raw.engine
                                || raw.current_engine
                                || payload.engine
                                || ''
                        );
                        const sessionError = session?.error || session?.reason || '';
                        const sessionRollback = session?.rollback_reason || '';
                        const runningModel = this.normalizeModelName(runningService?.model_name || runningService?.model || '');
                        const modelMatches = !normalizedModel || !runningModel || runningModel === normalizedModel;
                        const hasConflictingRunningService = services.some(service => {
                            if (service?.status !== 'running') return false;
                            const serviceEngine = normalizeEngineType(service.engine_type || service.engine || service.name || service.type);
                            if (!serviceEngine || serviceEngine === normalizedTarget) return false;
                            return true;
                        });
                        const serviceStable = !!runningService && currentEngine === normalizedTarget && modelMatches && !hasConflictingRunningService;

                        if (sessionError || sessionRollback) {
                            finish('error', sessionRollback ? `引擎切换已回滚：${sessionRollback}` : `引擎切换失败：${sessionError}`);
                            return;
                        }
                        if (sessionState.terminal && !sessionState.completed) {
                            finish('error', '引擎切换失败或已回滚');
                            return;
                        }

                        if (serviceStable) {
                            this._engineSwitchStableCount += 1;
                            if (this._engineSwitchStableCount >= this._engineSwitchStableThreshold) {
                                finish('success', `引擎切换成功：${engineDisplayName(normalizedTarget)} 已稳定运行`, true);
                                return;
                            }
                        } else {
                            this._engineSwitchStableCount = 0;
                        }
                        if (sessionState.completed && serviceStable) {
                            finish('success', `引擎切换成功：${engineDisplayName(normalizedTarget)} 已完成切换`, true);
                            return;
                        }

                        this._engineSwitchPollTimer = setTimeout(loop, this._engineSwitchPollInterval);
                    } catch (e) {
                        this._engineSwitchPollTimer = setTimeout(loop, 3000);
                    }
                };
                loop();
            },
            async loadEngineConfig(showMessage = true) {
                const editor = document.getElementById('aios-engine-config-editor');
                if (!editor || editor.dataset.dirty === 'true') return;
                try {
                    const result = await adminFetch('/api/engine/config');
                    const payload = result.data || result || {};
                    this.setEngineConfigSnapshot(payload);
                    editor.value = JSON.stringify(payload, null, 2);
                    editor.oninput = () => { editor.dataset.dirty = 'true'; };
                    if (showMessage) showToast('引擎配置已刷新', 'success');
                } catch (e) {
                    if (showMessage) showToast(`加载引擎配置失败: ${e.message}`, 'error');
                }
            },
            async saveEngineConfig() {
                const editor = document.getElementById('aios-engine-config-editor');
                if (!editor) return;
                let payload;
                try {
                    payload = JSON.parse(editor.value || '{}');
                } catch {
                    showToast('引擎配置 JSON 格式无效', 'warning');
                    return;
                }
                try {
                    const result = await adminFetch('/api/engine/config', { method: 'PUT', body: JSON.stringify(payload) });
                    if (result.detail || result.error) {
                        showToast(`保存引擎配置失败: ${result.detail || result.error}`, 'error');
                        return;
                    }
                    editor.dataset.dirty = 'false';
                    this.setEngineConfigSnapshot(payload);
                    showToast('引擎配置已保存', 'success');
                    this.refresh();
                } catch (e) {
                    showToast(`保存引擎配置失败: ${e.message}`, 'error');
                }
            },
            refreshHistory() {
                this.refreshHistoryData();
            },
            setTimeRange(range) {
                this.currentRange = this.normalizeHistoryRange(range);
                document.querySelectorAll('.aios-p-range-btn').forEach(b => {
                    b.classList.toggle('active', b.dataset.range === this.currentRange);
                });
                this.refreshHistoryData().catch((e) => {
                    showToast(`GPU 历史图刷新失败: ${e.message}`, 'warning');
                });
            },
        },
        model: {
            _downloadPolling: null,
            _switchPolling: null,
            _switchTaskId: '',
            _switchTargetModel: '',
            _switchPollDeadlineAt: 0,
            _switchPollIntervalMs: 3000,
            _switchPollTimeoutMs: 660000,
            _switchWs: null,
            _downloadWs: null,
            _realtimeStarted: false,
            isSwitching: false,
            actionLoading: false,
            currentModel: '',
            currentEngine: '',
            setActionStatus(type, message) {
                const el = document.getElementById('aios-switch-status');
                if (!el) return;
                if (!message) {
                    el.innerHTML = '';
                    return;
                }
                el.innerHTML = `<div class="aios-p-inline-status aios-p-inline-status-${type || 'info'}"><i class="fas ${type === 'error' ? 'fa-circle-exclamation' : type === 'success' ? 'fa-circle-check' : 'fa-circle-info'}"></i><span>${escapeHtml(message)}</span></div>`;
            },
            clearSwitchPolling() {
                if (this._switchPolling) {
                    clearTimeout(this._switchPolling);
                    this._switchPolling = null;
                }
                this._switchTaskId = '';
                this._switchTargetModel = '';
                this._switchPollDeadlineAt = 0;
            },
            initRealtime() {
                if (this._realtimeStarted || typeof WebSocket === 'undefined') return;
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const configuredHosts = Array.isArray(window.AIOS_WS_BASES) ? window.AIOS_WS_BASES : [];
                const currentPort = window.location.port || (window.location.protocol === 'https:' ? '443' : '80');
                const hosts = configuredHosts.length > 0
                    ? configuredHosts
                    : (['35000', '35001'].includes(currentPort) ? [`${protocol}//${window.location.host}`] : []);
                if (hosts.length === 0) return;
                this._realtimeStarted = true;
                const connect = (path, onMessage) => {
                    let idx = 0;
                    const tryNext = () => {
                        if (idx >= hosts.length) return;
                        try {
                            const ws = new WebSocket(`${hosts[idx++]}${path}`);
                            ws.onmessage = (event) => {
                                try { onMessage(JSON.parse(event.data)); } catch {}
                            };
                            ws.onerror = () => ws.close();
                            ws.onclose = () => {
                                if (idx < hosts.length) setTimeout(tryNext, 1000);
                            };
                            return ws;
                        } catch {
                            tryNext();
                        }
                    };
                    return tryNext();
                };
                this._switchWs = connect('/ws/model-switch', (msg) => {
                    if (msg.type === 'switch_state_sync' || msg.session || msg.is_switching !== undefined) {
                        this.renderSwitchingStatus({ data: msg });
                    }
                    if (msg.type && msg.type.includes('switch')) {
                        setTimeout(() => this.refresh(), 800);
                    }
                });
                this._downloadWs = connect('/ws/download', (msg) => {
                    if (msg.type && msg.type.includes('download')) {
                        this.refreshDownloadList();
                    }
                });
            },
            async refresh() {
                try {
                    const [aggData, switchData, engineData] = await Promise.all([
                        adminFetch('/api/model-switch/aggregated'),
                        adminFetch('/api/model-switch/switch-status'),
                        adminFetch('/api/engine/status')
                    ]);
                    this.renderBanner(aggData, engineData);
                    this.renderSwitchingStatus(switchData);
                    this.renderModelList(aggData);
                    this.populateModelSelect(aggData);
                    this.populateEngineSelect(engineData);
                    this.refreshDownloadList();
                    this.refreshPool();
                    if (!this.isSwitching && !this.actionLoading) this.setActionStatus('', '');
                } catch (e) {
                    const el = document.getElementById('aios-model-banner');
                    if (el) el.innerHTML = errorHTML(e.message);
                    if (this.actionLoading) this.setActionStatus('error', e.message);
                }
            },
            renderBanner(aggData, engineData) {
                const aggResult = aggData.data || aggData;
                const groups = aggResult.groups || [];
                const currentModel = aggResult.current_model || null;
                const engResult = engineData.data || engineData;
                const engRaw = engResult.current || engResult;
                const services = engRaw.services || engRaw.engines || [];
                let currentEngine = '-', currentPort = '-', engineHealth = '-';
                for (const s of services) {
                    if (s.status === 'running') {
                        currentEngine = s.engine_type || '-';
                        currentPort = s.port ?? '-';
                        engineHealth = s.health || '-';
                    }
                }
                this.currentModel = currentModel || '';
                this.currentEngine = normalizeEngineType(currentEngine);
                this.currentPort = currentPort;
                window.AiosManager.gpu.pendingTargetEngine = this.currentEngine;
                const modelDisplay = currentModel || '-';
                const engineDisplay = engineDisplayName(currentEngine);
                const el = document.getElementById('aios-model-banner');
                if (el) {
                    el.innerHTML = `
                        <div class="aios-p-banner-title">当前运行状态</div>
                        <div class="aios-p-banner-cards">
                            <div class="aios-p-banner-item"><div class="aios-p-banner-icon"><i class="fas fa-bolt"></i></div><div class="aios-p-banner-info"><div class="aios-p-banner-label">引擎</div><div class="aios-p-banner-value aios-p-value-active">${engineDisplay}</div></div></div>
                            <div class="aios-p-banner-item"><div class="aios-p-banner-icon"><i class="fas fa-cube"></i></div><div class="aios-p-banner-info"><div class="aios-p-banner-label">模型</div><div class="aios-p-banner-value aios-p-value-active">${modelDisplay}</div></div></div>
                            <div class="aios-p-banner-item"><div class="aios-p-banner-icon"><i class="fas fa-hashtag"></i></div><div class="aios-p-banner-info"><div class="aios-p-banner-label">端口</div><div class="aios-p-banner-value">${currentPort}</div></div></div>
                        </div>`;
                }
            },
            renderSwitchingStatus(switchData) {
                const data = switchData.data || switchData;
                const el = document.getElementById('aios-p-switching-banner');
                if (!el) return;
                const isSwitching = data.is_switching ?? false;
                this.isSwitching = !!isSwitching;
                const session = data.session || null;
                if (isSwitching && session) {
                    this.actionLoading = true;
                    const progress = session.overall_progress ?? 0;
                    const target = session.target_model || '-';
                    const actionText = session.action === 'switch' ? '切换' : session.action === 'start' ? '启动' : '停止';
                    const rollback = session.rollback_reason ? `<div class="aios-p-inline-status aios-p-inline-status-error" style="margin-top:var(--space-sm);"><i class="fas fa-rotate-left"></i><span>已触发回滚: ${escapeHtml(session.rollback_reason)}</span></div>` : '';
                    const phasesHtml = (session.phases || []).map(p => {
                        const statusIcon = p.status === 'running' ? 'fa-spinner fa-spin' : p.status === 'success' ? 'fa-check' : p.status === 'failed' ? 'fa-times' : 'fa-clock';
                        return `<div style="display:flex;align-items:center;gap:8px;padding:4px 0;"><i class="fas ${statusIcon}" style="width:16px;"></i><span style="font-size:12px;color:var(--text-secondary);">${p.name}</span></div>`;
                    }).join('');
                    this.setActionStatus('info', `${actionText}任务进行中：${target} · ${progress}%`);
                    el.innerHTML = `<div class="aios-p-status-banner" style="border-color:rgba(var(--color-warning-rgb),0.3);">
                        <div class="aios-p-banner-title" style="color:var(--color-warning);">正在${actionText}模型</div>
                        <div style="display:flex;align-items:center;gap:var(--space-lg);">
                            <div style="flex:1;"><div style="font-size:14px;font-weight:600;color:var(--text-primary);">${target}</div><div style="margin-top:8px;">${phasesHtml}</div>${rollback}</div>
                            <div style="width:100px;"><div class="aios-p-progress-bar" style="height:8px;"><div class="aios-p-progress-fill aios-p-warning" style="width:${progress}%"></div></div><div style="font-size:11px;color:var(--text-muted);text-align:center;margin-top:4px;">${progress}%</div></div>
                        </div>
                        <div style="margin-top:var(--space-md);"><button class="aios-p-btn aios-p-btn-sm aios-p-btn-danger" data-action="cancel-switch"><i class="fas fa-times"></i> 取消</button></div>
                    </div>`;
                } else {
                    this.actionLoading = false;
                    this.clearSwitchPolling();
                    if (session?.completed_successfully) {
                        this.setActionStatus('success', `切换完成：${session.target_model || this.currentModel || '-'}`);
                        setTimeout(() => {
                            this.setActionStatus('', '');
                        }, 5000);
                    } else if (session?.error || session?.rollback_reason) {
                        this.setActionStatus('error', session.error || session.rollback_reason);
                    } else if (!this.actionLoading) {
                        this.setActionStatus('', '');
                    }
                    el.innerHTML = '';
                }
            },
            populateModelSelect(aggData) {
                const aggResult = aggData.data || aggData;
                const groups = aggResult.groups || [];
                const select = document.getElementById('aios-switch-model');
                if (!select) return;
                const currentModel = aggResult.current_model || '';
                const previousValue = select.value || '';
                const preserveUserSelection = previousValue && previousValue !== currentModel && !this.isSwitching && !this.actionLoading;
                let hasPreviousValue = false;
                let hasCurrentValue = false;
                const modelOptions = groups.map(g => {
                    const variants = Array.isArray(g.variants) && g.variants.length > 0
                        ? g.variants
                        : [{ name: g.base_name, is_current: g.base_name === currentModel, path_exists: true }];
                    const options = variants.map(v => {
                        const name = v.name || g.base_name;
                        if (name === previousValue) hasPreviousValue = true;
                        if (name === currentModel || v.is_current) hasCurrentValue = true;
                        const sizeMb = Number(v.size_mb || 0);
                        const missingWeights = v.path_exists === true && sizeMb > 0 && sizeMb < 100 && !v.running && !v.is_current;
                        const disabled = v.path_exists === false || missingWeights ? ' disabled' : '';
                        const state = v.running || v.is_current ? '运行中' : (v.path_exists === false ? '未下载' : missingWeights ? '权重缺失' : '已下载');
                        const engine = engineDisplayName(v.backend_type || 'vllm');
                        return `<option value="${escapeHtml(name)}"${disabled}>${escapeHtml(name)} · ${engine} · ${state}</option>`;
                    }).join('');
                    if (variants.length === 1) return options;
                    return `<optgroup label="${escapeHtml(g.base_name)}">${options}</optgroup>`;
                }).join('');
                const placeholder = currentModel ? '' : '<option value="" selected disabled>请选择模型</option>';
                select.innerHTML = `${placeholder}${modelOptions}`;
                const nextValue = preserveUserSelection && hasPreviousValue ? previousValue : (hasCurrentValue ? currentModel : '');
                if (nextValue) select.value = nextValue;
            },
            populateEngineSelect(engineData) {
                const result = engineData.data || engineData;
                const raw = result.current || result;
                const services = raw.services || raw.engines || [];
                const select = document.getElementById('aios-switch-engine');
                if (!select) return;
                const engineTypes = ['vllm', 'sglang', 'llamacpp'];
                const engineOptions = engineTypes.map(t => {
                    const service = services.find(s => normalizeEngineType(s.engine_type || s.name || s.type) === t);
                    const running = service && service.status === 'running';
                    const enabled = window.AiosManager.gpu.isEngineEnabled(t);
                    const cfg = window.AiosManager.gpu.getEngineConfig(t);
                    const configured = t === 'vllm' || !!service || Object.keys(cfg || {}).length > 0;
                    const disabled = !enabled || !configured;
                    const suffix = !configured ? ' (未配置)' : (!enabled ? ' (已禁用)' : (running ? ' (当前)' : ' (可切换)'));
                    return `<option value="${t}"${running ? ' selected' : ''}${disabled ? ' disabled' : ''}>${engineDisplayName(t)}${suffix}</option>`;
                }).join('');
                const hasUsableEngine = engineTypes.some(t => {
                    const cfg = window.AiosManager.gpu.getEngineConfig(t);
                    const configured = t === 'vllm' || services.some(s => normalizeEngineType(s.engine_type || s.name || s.type) === t) || Object.keys(cfg || {}).length > 0;
                    return configured && window.AiosManager.gpu.isEngineEnabled(t);
                });
                const placeholder = hasUsableEngine ? '' : '<option value="" selected disabled>无可用引擎</option>';
                select.innerHTML = `${placeholder}${engineOptions}`;
            },
            renderModelList(aggData) {
                const aggResult = aggData.data || aggData;
                const groups = aggResult.groups || [];
                const el = document.getElementById('aios-model-list');
                if (!el) return;
                if (!groups || groups.length === 0) {
                    el.innerHTML = emptyHTML('暂无模型，请通过模型下载添加');
                    return;
                }
                el.innerHTML = `<div class="aios-p-models-list">${groups.map(g => {
                    const variants = g.variants || [];
                    const groupName = g.base_name;
                    const runningCount = variants.filter(v => v.running || v.is_current).length;
                    const totalSize = g.total_size_mb ? `${(g.total_size_mb / 1024).toFixed(1)}GB` : '-';
                    return `<div class="aios-p-model-group">
                        <div class="aios-p-model-group-head">
                            <div class="aios-p-model-group-title">
                                <span class="aios-p-model-group-name">${groupName}</span>
                                <span class="aios-p-model-group-count">${variants.length} 个变体</span>
                            </div>
                            <div class="aios-p-model-group-stats">
                                <span class="aios-p-model-group-stat">${runningCount > 0 ? `<span style="color:var(--color-success);">${runningCount} 运行</span>` : '未运行'}</span>
                                <span class="aios-p-model-group-stat">总大小: ${totalSize}</span>
                            </div>
                        </div>
                        <div class="aios-p-model-grid">${variants.map(v => {
                            const isRunning = v.running || false;
                            const isCurrent = v.is_current || false;
                            const vName = v.name || groupName;
                            const vEngine = v.backend_type || 'vllm';
                            const vPort = v.port ?? '-';
                            const vSize = v.size_mb ? `${(v.size_mb / 1024).toFixed(1)}GB` : '-';
                            const vReqMem = v.required_memory || '-';
                            const vPathExists = v.path_exists !== false;
                            const vMultimodal = v.multimodal || v.supports_images || false;
                            const isBusy = this.isSwitching || this.actionLoading;
                            return `<div class="aios-p-model-item ${isCurrent ? 'aios-p-current-model' : ''} ${isBusy ? 'aios-p-model-item-busy' : ''}">
                                <div class="aios-p-model-header">
                                    <div class="aios-p-model-title-wrap">
                                        <div class="aios-p-model-name">${vName}</div>
                                        <div class="aios-p-model-tags">
                                            <span class="aios-p-model-status ${isRunning ? 'aios-p-running' : 'aios-p-stopped'}">${isRunning ? '运行中' : (vPathExists ? '已下载' : '未下载')}</span>
                                            ${isCurrent ? '<span class="aios-p-badge aios-p-badge-primary">当前</span>' : ''}
                                            ${this.isSwitching && isCurrent ? '<span class="aios-p-model-chip aios-p-model-chip-warning">切换中</span>' : ''}
                                            <span class="aios-p-model-chip">${engineDisplayName(vEngine)}</span>
                                            ${vMultimodal ? '<span class="aios-p-model-chip" style="background:rgba(var(--color-success-rgb),0.08);border-color:rgba(var(--color-success-rgb),0.18);color:var(--color-success);">多模态</span>' : ''}
                                        </div>
                                    </div>
                                </div>
                                <div class="aios-p-model-info-grid">
                                    <div class="aios-p-model-info-card"><div class="aios-p-model-info-label">端口</div><div class="aios-p-model-info-value">${vPort}</div></div>
                                    <div class="aios-p-model-info-card"><div class="aios-p-model-info-label">大小</div><div class="aios-p-model-info-value">${vSize}</div></div>
                                    <div class="aios-p-model-info-card"><div class="aios-p-model-info-label">需显存</div><div class="aios-p-model-info-value">${vReqMem}</div></div>
                                </div>
                                <div class="aios-p-model-actions">
                                    ${!vPathExists ? `<button class="aios-p-btn aios-p-btn-sm" data-action="download-by-name" data-model="${vName}" ${isBusy ? 'disabled' : ''}><i class="fas fa-cloud-download-alt"></i> 下载</button>` : ''}
                                    ${vPathExists && !isRunning ? `<button class="aios-p-btn aios-p-btn-sm aios-p-btn-success" data-action="start-model" data-model="${vName}" ${isBusy ? 'disabled' : ''}><i class="fas fa-play"></i> 启动</button>` : ''}
                                    ${isRunning && !isCurrent ? `<button class="aios-p-btn aios-p-btn-sm aios-p-btn-primary" data-action="switch-to-model" data-model="${vName}" data-engine="${vEngine}" ${isBusy ? 'disabled' : ''}><i class="fas fa-exchange-alt"></i> 切换</button>` : ''}
                                    ${isRunning ? `<button class="aios-p-btn aios-p-btn-sm aios-p-btn-danger" data-action="stop-model" data-model="${vName}" ${isBusy ? 'disabled' : ''}><i class="fas fa-stop"></i> 停止</button>` : ''}
                                </div>
                            </div>`;
                        }).join('')}</div>
                    </div>`;
                }).join('')}</div>`;
            },
            _searchPayload(result) {
                const item = result || {};
                const name = item.model_id || item.model_name || item.name || item.id || '';
                return {
                    name,
                    source: item.source || 'search',
                    size_b: item.size_b ?? item.params_b ?? item.parameters_b ?? null,
                    quant: item.quant || item.quantization || null,
                    required_gb: item.required_gb ?? item.estimated_memory_gb ?? item.memory_gb ?? null,
                    feasible: item.feasible ?? item.can_run ?? item.runnable ?? null,
                };
            },
            renderSearchResults(data, title = '搜索结果') {
                const el = document.getElementById('aios-search-results');
                if (!el) return;
                const payload = data.data || data || {};
                const list = payload.results || payload.models || payload.candidates || (Array.isArray(payload) ? payload : []);
                if (!Array.isArray(list) || list.length === 0) {
                    el.innerHTML = emptyHTML('暂无匹配模型');
                    return;
                }
                el.innerHTML = `<div style="font-size:13px;font-weight:600;color:var(--text-primary);margin-bottom:8px;">${escapeHtml(title)}</div>
                    <div style="display:flex;flex-direction:column;gap:var(--space-sm);">${list.map(raw => {
                        const item = this._searchPayload(raw);
                        const encodedName = encodeURIComponent(item.name);
                        const encodedSource = encodeURIComponent(item.source || 'search');
                        const feasible = item.feasible === true;
                        const feasibilityText = item.feasible === null || item.feasible === undefined ? '未知' : (feasible ? '可运行' : '显存不足');
                        const req = item.required_gb != null ? `${formatNumber(item.required_gb, 1)}GB` : '-';
                        const size = item.size_b != null ? `${formatNumber(item.size_b, 1)}B` : '-';
                        return `<div class="aios-p-banner-item" style="align-items:flex-start;gap:var(--space-md);">
                            <div class="aios-p-banner-info" style="flex:1;min-width:220px;">
                                <div class="aios-p-banner-label">${escapeHtml(item.source || '-')}</div>
                                <div class="aios-p-banner-value" style="font-size:14px;">${escapeHtml(item.name || '-')}</div>
                                <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:6px;font-size:12px;color:var(--text-secondary);">
                                    <span>大小: ${escapeHtml(size)}</span>
                                    <span>量化: ${escapeHtml(item.quant || '-')}</span>
                                    <span>需显存: ${escapeHtml(req)}</span>
                                    <span style="color:${feasible ? 'var(--color-success)' : 'var(--color-warning)'}">${feasibilityText}</span>
                                </div>
                            </div>
                            <div class="aios-p-form-actions">
                                <button class="aios-p-btn aios-p-btn-sm" onclick="AiosManager.model.registerSearchResult('${encodedName}','${encodedSource}',${Number(item.required_gb) || 0},${item.feasible === true})"><i class="fas fa-plus"></i> 入池</button>
                                <button class="aios-p-btn aios-p-btn-sm aios-p-btn-primary" onclick="AiosManager.model.downloadEncoded('${encodedName}','${encodedSource}')"><i class="fas fa-download"></i> 下载</button>
                            </div>
                        </div>`;
                    }).join('')}</div>`;
            },
            async searchModels() {
                const keyword = document.getElementById('aios-search-keyword').value.trim();
                const source = document.getElementById('aios-search-source').value;
                const sort = document.getElementById('aios-search-sort').value;
                if (!keyword) { showToast('请输入搜索关键词', 'warning'); return; }
                const el = document.getElementById('aios-search-results');
                if (el) el.innerHTML = loadingHTML('搜索中...');
                try {
                    const query = new URLSearchParams({ keyword, source, limit: '20', sort });
                    const result = await adminFetch(`/api/model-switch/search?${query.toString()}`);
                    this.renderSearchResults(result, '搜索结果');
                } catch (e) {
                    if (el) el.innerHTML = errorHTML(e.message);
                }
            },
            async recommendModels() {
                const keyword = document.getElementById('aios-search-keyword').value.trim();
                const source = document.getElementById('aios-search-source').value;
                if (!keyword) { showToast('请输入搜索关键词', 'warning'); return; }
                const el = document.getElementById('aios-search-results');
                if (el) el.innerHTML = loadingHTML('计算显存优选...');
                try {
                    const query = new URLSearchParams({ keyword, source });
                    const result = await adminFetch(`/api/model-switch/recommend?${query.toString()}`);
                    this.renderSearchResults(result, '显存优选推荐');
                } catch (e) {
                    if (el) el.innerHTML = errorHTML(e.message);
                }
            },
            async registerSearchResult(encodedName, encodedSource, requiredGb = 0, feasible = false) {
                const modelName = decodeURIComponent(encodedName);
                const source = decodeURIComponent(encodedSource);
                try {
                    await adminFetch('/api/model-switch/pool/register', {
                        method: 'POST',
                        body: JSON.stringify({ model_name: modelName, source, required_gb: requiredGb || null, feasible })
                    });
                    showToast(`${modelName} 已加入模型池`, 'success');
                    this.refreshPool();
                } catch (e) {
                    showToast(`入池失败: ${e.message}`, 'error');
                }
            },
            downloadEncoded(encodedName, encodedSource) {
                const source = decodeURIComponent(encodedSource);
                document.getElementById('aios-download-model-name').value = decodeURIComponent(encodedName);
                document.getElementById('aios-download-source').value = source === 'huggingface' ? 'hf' : source;
                this.download();
            },
            async refreshPool() {
                const el = document.getElementById('aios-model-pool');
                if (!el) return;
                try {
                    const result = await adminFetch('/api/model-switch/pool');
                    const payload = result.data || result || {};
                    const models = payload.models || payload.entries || (Array.isArray(payload) ? payload : []);
                    if (!Array.isArray(models) || models.length === 0) {
                        el.innerHTML = emptyHTML('模型池为空');
                        return;
                    }
                    const totalSize = models.reduce((sum, m) => sum + (Number(m.size_bytes || m.total_bytes || 0) || 0), 0);
                    const completed = models.filter(m => (m.download_status || m.status) === 'completed' || m.local_path || m.path).length;
                    el.innerHTML = `<div class="aios-p-stats-grid" style="margin-bottom:var(--space-md);">
                        <div class="aios-p-stat-card"><div class="aios-p-stat-body"><div class="aios-p-stat-label">模型数</div><div class="aios-p-stat-value">${models.length}</div></div></div>
                        <div class="aios-p-stat-card"><div class="aios-p-stat-body"><div class="aios-p-stat-label">可加载</div><div class="aios-p-stat-value">${completed}</div></div></div>
                        <div class="aios-p-stat-card"><div class="aios-p-stat-body"><div class="aios-p-stat-label">总大小</div><div class="aios-p-stat-value">${totalSize ? formatBytes(totalSize) : '-'}</div></div></div>
                    </div>
                    <div style="display:flex;flex-direction:column;gap:var(--space-sm);">${models.map(m => {
                        const key = m.key || m.name || m.model_name || m.model_id || '';
                        const display = m.name || m.model_name || key;
                        const encodedKey = encodeURIComponent(key);
                        const status = m.running_status || m.download_status || m.status || '-';
                        const source = m.source || '-';
                        const req = m.required_gb ?? m.estimated_memory_gb ?? null;
                        return `<div class="aios-p-banner-item" style="flex-wrap:wrap;">
                            <div class="aios-p-banner-info" style="flex:2;min-width:220px;">
                                <div class="aios-p-banner-label">${escapeHtml(source)} · ${escapeHtml(status)}</div>
                                <div class="aios-p-banner-value" style="font-size:14px;">${escapeHtml(display)}</div>
                                <div style="font-size:12px;color:var(--text-secondary);margin-top:4px;">需显存: ${req != null ? `${formatNumber(req, 1)}GB` : '-'} · ${escapeHtml(m.local_path || m.path || '')}</div>
                            </div>
                            <div class="aios-p-form-actions">
                                <button class="aios-p-btn aios-p-btn-sm aios-p-btn-success" onclick="AiosManager.model.loadPoolModel('${encodedKey}')"><i class="fas fa-play"></i> 一键加载</button>
                                <button class="aios-p-btn aios-p-btn-sm aios-p-btn-danger" onclick="AiosManager.model.deletePoolModel('${encodedKey}')"><i class="fas fa-trash"></i> 删除</button>
                            </div>
                        </div>`;
                    }).join('')}</div>`;
                } catch (e) {
                    el.innerHTML = errorHTML(e.message);
                }
            },
            async loadPoolModel(encodedKey) {
                const key = decodeURIComponent(encodedKey);
                const engine = document.getElementById('aios-switch-engine')?.value || 'vllm';
                try {
                    const result = await adminFetch(`/api/model-switch/pool/${encodeURIComponent(key)}/load`, {
                        method: 'POST',
                        body: JSON.stringify({ engine })
                    });
                    if (result.success || result.data?.success || result.status === 'success') {
                        showToast(`${key} 加载任务已提交`, 'success');
                    } else {
                        showToast(`加载失败: ${result.detail || result.error || result.reason || '未知错误'}`, 'error');
                    }
                    this.refresh();
                } catch (e) {
                    showToast(`加载失败: ${e.message}`, 'error');
                }
            },
            async deletePoolModel(encodedKey) {
                const key = decodeURIComponent(encodedKey);
                try {
                    const result = await adminFetch(`/api/model-switch/pool/${encodeURIComponent(key)}?remove_files=false`, { method: 'DELETE' });
                    if (result.deleted || result.data?.deleted) showToast(`${key} 已从模型池移除`, 'success');
                    else showToast(`删除失败: ${result.detail || result.reason || '未知错误'}`, 'error');
                    this.refreshPool();
                } catch (e) {
                    showToast(`删除失败: ${e.message}`, 'error');
                }
            },
            async syncPoolConfig() {
                try {
                    await adminFetch('/api/model-switch/pool/sync-config', { method: 'POST' });
                    showToast('模型池已同步到配置', 'success');
                } catch (e) {
                    showToast(`同步失败: ${e.message}`, 'error');
                }
            },
            async switchModel() {
                const modelInput = document.getElementById('aios-switch-model');
                const engineInput = document.getElementById('aios-switch-engine');
                const portInput = document.getElementById('aios-switch-port');
                if (!modelInput) return;
                const modelName = modelInput.value;
                const engineType = engineInput ? engineInput.value : 'vllm';
                const port = portInput ? portInput.value : null;
                if (!modelName) { showToast('请选择模型', 'warning'); return; }
                const selectedEngineOption = engineInput?.selectedOptions?.[0] || null;
                if (!engineType || selectedEngineOption?.disabled) {
                    showToast('请选择已配置的引擎', 'warning');
                    return;
                }
                if (this.isSwitching || this.actionLoading) {
                    showToast('已有模型切换任务进行中，请等待完成或取消后再操作', 'warning');
                    return;
                }
                this.actionLoading = true;
                this.setActionStatus('info', `准备切换到 ${modelName} · ${engineDisplayName(engineType)}`);
                try {
                    const currentModel = this.currentModel || '';
                    const currentEngine = normalizeEngineType(this.currentEngine || '');
                    if (modelName === currentModel && normalizeEngineType(engineType) === currentEngine) {
                        this.setActionStatus('success', `${modelName} 已在 ${engineDisplayName(engineType)} 上运行`);
                        showToast(`${modelName} 已在 ${engineDisplayName(engineType)} 上运行`, 'info');
                        return;
                    }
                    const confirmed = await showConfirm(`确认切换到 ${modelName} (${engineDisplayName(engineType)})？该操作会重启推理服务。`);
                    if (!confirmed) {
                        this.setActionStatus('', '');
                        return;
                    }
                    if (normalizeEngineType(engineType) !== currentEngine) {
                        const engineBody = { model_name: modelName, engine_type: normalizeEngineType(engineType) };
                        if (port) engineBody.port = parseInt(port);
                        this.setActionStatus('info', `正在切换引擎到 ${engineDisplayName(engineType)}...`);
                        const engineResult = await adminFetch('/api/engine/switch', {
                            method: 'POST',
                            body: JSON.stringify(engineBody)
                        });
                        if (engineResult.success || engineResult.data?.success) {
                            const reason = engineResult.data?.reason || engineResult.reason;
                            const message = reason === 'already_running_same_engine'
                                ? `${modelName} 已在 ${engineDisplayName(engineType)} 上运行`
                                : `引擎切换任务已提交: ${engineDisplayName(engineType)}`;
                            this.setActionStatus(reason === 'already_running_same_engine' ? 'success' : 'info', message);
                            showToast(message, reason === 'already_running_same_engine' ? 'info' : 'success');
                            const normalizedEngine = normalizeEngineType(engineType);
                            window.AiosManager.gpu.switchingEngine = normalizedEngine;
                            window.AiosManager.gpu.pendingTargetEngine = normalizedEngine;
                            window.AiosManager.gpu._engineSwitchTargetEngine = normalizedEngine;
                            window.AiosManager.gpu._engineSwitchTargetModel = window.AiosManager.gpu.normalizeModelName(modelName);
                            window.AiosManager.gpu._engineSwitchTargetPort = port ? parseInt(port) : null;
                            window.AiosManager.gpu._engineSwitchDeadlineAt = Date.now() + window.AiosManager.gpu._engineSwitchTimeoutMs;
                            window.AiosManager.gpu.pollEngineSwitchStatus(normalizedEngine, modelName);
                            setTimeout(() => this.refresh(), 3000);
                            window.AiosManager.gpu.refresh(false);
                        } else {
                            const detail = engineResult.detail || engineResult.error || engineResult.data?.detail || engineResult.data?.reason || '未知错误';
                            this.setActionStatus('error', detail);
                            showToast(`引擎切换失败: ${detail}`, 'error');
                        }
                        return;
                    }
                    const body = { modelName, engineType };
                    if (port) body.port = parseInt(port);
                    this.setActionStatus('info', `正在提交 ${modelName} 的切换任务...`);
                    const result = await adminFetch('/api/model-switch/switch', {
                        method: 'POST',
                        body: JSON.stringify(body)
                    });
                    const data = result.data || result;
                    if (data.taskId) {
                        this._switchTaskId = data.taskId;
                        this._switchTargetModel = modelName;
                        this._switchPollDeadlineAt = Date.now() + this._switchPollTimeoutMs;
                        this.setActionStatus('info', `切换任务已提交：${modelName}`);
                        showToast('切换任务已提交', 'info');
                        this.pollSwitchStatus(data.taskId, modelName);
                    } else if (data.success) {
                        this.setActionStatus('success', `切换到 ${modelName} 成功`);
                        showToast(`切换到 ${modelName} 成功`, 'success');
                        this.refresh();
                        window.AiosManager.gpu.refresh(false);
                    } else {
                        this.setActionStatus('error', data.error || '未知错误');
                        showToast(`切换失败: ${data.error || '未知错误'}`, 'error');
                    }
                } catch (e) {
                    this.setActionStatus('error', e.message);
                    showToast(`切换失败: ${e.message}`, 'error');
                } finally {
                    if (!this._switchPolling && !this.isSwitching) this.actionLoading = false;
                }
            },
            async switchTo(modelName, backendType) {
                if (this.isSwitching || this.actionLoading) {
                    showToast('已有模型切换任务进行中，请等待完成或取消后再操作', 'warning');
                    return;
                }
                this.actionLoading = true;
                this.setActionStatus('info', `准备切换到 ${modelName}`);
                try {
                    const confirmed = await showConfirm(`确认切换到 ${modelName}？该操作会重启推理服务。`);
                    if (!confirmed) {
                        this.setActionStatus('', '');
                        return;
                    }
                    const result = await adminFetch('/api/model-switch/switch', {
                        method: 'POST',
                        body: JSON.stringify({ modelName, engineType: normalizeEngineType(backendType), async: true })
                    });
                    const data = result.data || result;
                    if (data.taskId) {
                        this.setActionStatus('info', `切换任务已提交：${modelName}`);
                        showToast('切换任务已提交', 'info');
                        this.pollSwitchStatus(data.taskId, modelName);
                    } else if (data.success) {
                        this.setActionStatus('success', `切换到 ${modelName} 成功`);
                        showToast(`切换到 ${modelName} 成功`, 'success');
                        this.refresh();
                        window.AiosManager.gpu.refresh(false);
                    } else {
                        this.setActionStatus('error', data.error || '未知错误');
                        showToast(`切换失败: ${data.error || '未知错误'}`, 'error');
                    }
                } catch (e) {
                    this.setActionStatus('error', e.message);
                    showToast(`切换失败: ${e.message}`, 'error');
                } finally {
                    if (!this._switchPolling && !this.isSwitching) this.actionLoading = false;
                }
            },
            async start(modelName) {
                try {
                    const confirmed = await showConfirm(`确认启动 ${modelName}？`);
                    if (!confirmed) return;
                    const result = await adminFetch('/api/model-switch/start', { method: 'POST', body: JSON.stringify({ modelName }) });
                    if (result.success || result.data?.success) {
                        showToast(`启动 ${modelName} 成功`, 'success');
                    } else {
                        showToast(`启动失败: ${result.error || result.data?.error || '未知错误'}`, 'error');
                    }
                    this.refresh();
                } catch (e) { showToast(`启动失败: ${e.message}`, 'error'); }
            },
            async stop(modelName) {
                try {
                    const confirmed = await showConfirm(`确认停止 ${modelName}？当前推理服务会中断。`);
                    if (!confirmed) return;
                    const result = await adminFetch('/api/model-switch/stop', { method: 'POST', body: JSON.stringify({ modelName }) });
                    if (result.success || result.data?.success) {
                        showToast(`停止 ${modelName} 成功`, 'success');
                    } else {
                        showToast(`停止失败: ${result.error || result.data?.error || '未知错误'}`, 'error');
                    }
                    this.refresh();
                    window.AiosManager.gpu.refresh();
                } catch (e) { showToast(`停止失败: ${e.message}`, 'error'); }
            },
            async cancelSwitch() {
                try {
                    await adminFetch('/api/model-switch/cancel', { method: 'POST' });
                    showToast('已取消切换', 'info');
                    this.refresh();
                } catch (e) { showToast(`取消失败: ${e.message}`, 'error'); }
            },
            pollSwitchStatus(taskId = '', targetModel = '') {
                if (this._switchPolling) {
                    clearTimeout(this._switchPolling);
                    this._switchPolling = null;
                }
                this._switchTaskId = taskId || '';
                this._switchTargetModel = targetModel || '';
                this._switchPollDeadlineAt = Date.now() + this._switchPollTimeoutMs;
                this.actionLoading = true;
                this.isSwitching = true;

                const finish = (type, message) => {
                    this.clearSwitchPolling();
                    this.actionLoading = false;
                    this.isSwitching = false;
                    if (message) this.setActionStatus(type, message);
                    if (message) showToast(message, type === 'error' ? 'error' : type === 'warning' ? 'warning' : 'success');
                    this.refresh();
                    window.AiosManager.gpu.refresh(false);
                };

                const loop = async () => {
                    if (Date.now() >= this._switchPollDeadlineAt) {
                        finish('warning', `切换超时：${targetModel || this._switchTargetModel || '目标模型'}`);
                        return;
                    }
                    try {
                        const switchStatus = await adminFetch('/api/model-switch/switch-status');
                        this.renderSwitchingStatus(switchStatus);
                        const switchData = switchStatus.data || switchStatus || {};
                        const session = switchData.session || null;
                        const target = session?.target_model || targetModel || this._switchTargetModel || '-';
                        if (switchData.is_switching) {
                            const progress = session?.overall_progress;
                            const progressText = Number.isFinite(Number(progress)) ? ` · ${progress}%` : '';
                            this.setActionStatus('info', `切换中：${target}${progressText}`);
                            this._switchPolling = setTimeout(loop, this._switchPollIntervalMs);
                            return;
                        }
                        if (session?.completed_successfully) {
                            finish('success', `切换完成：${target}`);
                            return;
                        }
                        if (session?.error || session?.rollback_reason) {
                            finish('error', session.error || session.rollback_reason);
                            return;
                        }
                        finish('success', `切换完成：${target}`);
                    } catch (e) {
                        this.setActionStatus('warning', `切换状态刷新失败，继续轮询：${e.message}`);
                        this._switchPolling = setTimeout(loop, this._switchPollIntervalMs);
                    }
                };
                loop();
            },
            async download() {
                const modelInput = document.getElementById('aios-download-model-name');
                const sourceInput = document.getElementById('aios-download-source');
                if (!modelInput) return;
                const modelName = modelInput.value.trim();
                const source = sourceInput ? sourceInput.value : 'hf';
                if (!modelName) { showToast('请输入模型ID', 'warning'); return; }
                try {
                    const result = await adminFetch('/api/model-switch/download', {
                        method: 'POST',
                        body: JSON.stringify({ model_name: modelName, source })
                    });
                    const data = result.data || result;
                    if (data.taskId) {
                        showToast(`下载任务已创建: ${modelName}`, 'success');
                        this.startDownloadPolling();
                    } else if (data.status === 'already_exists') {
                        showToast(`${modelName} 已存在本地`, 'info');
                        this.refresh();
                    } else if (data.status === 'queued') {
                        showToast(data.message || '下载排队中', 'warning');
                        this.startDownloadPolling();
                    } else if (data.detail) {
                        showToast(`下载失败: ${data.detail}`, 'error');
                    } else {
                        showToast(`下载失败: ${data.error || data.message || '未知错误'}`, 'error');
                    }
                } catch (e) {
                    showToast(`下载失败: ${e.message}`, 'error');
                }
            },
            downloadByName(modelName) {
                const modelInput = document.getElementById('aios-download-model-name');
                const sourceInput = document.getElementById('aios-download-source');
                if (modelInput) modelInput.value = modelName;
                if (sourceInput) sourceInput.value = 'hf';
                this.download();
            },
            startDownloadPolling() {
                if (this._downloadPolling) return;
                this._downloadPolling = setInterval(() => {
                    this.refreshDownloadList();
                }, 3000);
            },
            stopDownloadPolling() {
                if (this._downloadPolling) { clearInterval(this._downloadPolling); this._downloadPolling = null; }
            },
            async refreshDownloadList() {
                try {
                    const result = await adminFetch('/api/model-switch/downloads');
                    const tasks = result.data || result || [];
                    const el = document.getElementById('aios-download-tasks');
                    if (!el) return;
                    if (!Array.isArray(tasks) || tasks.length === 0) {
                        el.innerHTML = emptyHTML('暂无下载任务');
                        this.stopDownloadPolling();
                        return;
                    }
                    const hasActive = tasks.some(t => ['pending', 'downloading', 'retrying'].includes(t.status));
                    if (hasActive) this.startDownloadPolling();
                    else this.stopDownloadPolling();

                    el.innerHTML = `<div style="display:flex;flex-direction:column;gap:var(--space-md);">${tasks.map(t => {
                        const pct = t.progress_pct ?? 0;
                        const speed = t.speed_mbps ?? 0;
                        const eta = t.eta_seconds ?? null;
                        const etaStr = eta ? `${Math.floor(eta / 60)}m${Math.floor(eta % 60)}s` : '-';
                        const downloaded = formatBytes(t.downloaded_bytes ?? 0);
                        const total = t.total_bytes ? formatBytes(t.total_bytes) : '-';
                        const statusText = t.status === 'downloading' ? `下载中 ${pct}%` :
                            t.status === 'pending' ? '等待中' :
                            t.status === 'completed' ? '已完成' :
                            t.status === 'already_exists' ? '已存在' :
                            t.status === 'failed' ? '失败' :
                            t.status === 'retrying' ? '重试中' :
                            t.status === 'cancelled' ? '已取消' : t.status;
                        const statusColor = ['completed', 'already_exists'].includes(t.status) ? 'var(--color-success)' :
                            ['downloading', 'retrying'].includes(t.status) ? 'var(--color-primary)' :
                            ['failed', 'error'].includes(t.status) ? 'var(--color-danger)' :
                            ['pending', 'queued'].includes(t.status) ? 'var(--color-warning)' : 'var(--text-secondary)';
                        const progressBar = ['downloading', 'pending', 'retrying'].includes(t.status) ?
                            `<div class="aios-p-progress-bar" style="height:6px;margin-top:6px;"><div class="aios-p-progress-fill aios-${pct > 80 ? 'success' : 'warning'}" style="width:${pct}%"></div></div>` : '';
                        const actions = t.status === 'downloading' || t.status === 'pending' ?
                            `<button class="aios-p-btn aios-p-btn-sm aios-p-btn-danger" data-action="cancel-download" data-task-id="${t.task_id}"><i class="fas fa-times"></i> 取消</button>` :
                            t.status === 'failed' ?
                            `<button class="aios-p-btn aios-p-btn-sm aios-p-btn-primary" data-action="retry-download" data-task-id="${t.task_id}"><i class="fas fa-redo"></i> 重试</button>` : '';
                        return `<div class="aios-p-banner-item" style="flex-wrap:wrap;">
                            <div class="aios-p-banner-info" style="flex:2;min-width:200px;">
                                <div class="aios-p-banner-label">${t.model_name || '-'} (${t.source || 'hf'})</div>
                                <div style="font-size:12px;color:${statusColor};font-weight:600;">${statusText}${speed > 0 ? ` | ${speed}MB/s | ETA ${etaStr}` : ''}${downloaded ? ` | ${downloaded}/${total}` : ''}</div>
                                ${progressBar}
                                ${t.error_message ? `<div style="font-size:11px;color:var(--color-danger);margin-top:4px;">${t.error_message}</div>` : ''}
                            </div>
                            <div class="aios-p-form-actions">${actions}</div>
                        </div>`;
                    }).join('')}</div>`;

                    const justCompleted = tasks.filter(t => t.status === 'completed');
                    if (justCompleted.length > 0) {
                        for (const t of justCompleted) {
                            if (!this._notifiedCompleted?.has(t.task_id)) {
                                showToast(`${t.model_name} 下载完成`, 'success');
                                if (!this._notifiedCompleted) this._notifiedCompleted = new Set();
                                this._notifiedCompleted.add(t.task_id);
                                setTimeout(() => this.refresh(), 2000);
                            }
                        }
                    }
                } catch (e) {
                    const el = document.getElementById('aios-download-tasks');
                    if (el) el.innerHTML = errorHTML(e.message);
                }
            },
            async cancelDownload(taskId) {
                try {
                    const result = await adminFetch(`/api/model-switch/download/${taskId}`, { method: 'DELETE' });
                    if (result.data?.cancelled || result.cancelled) {
                        showToast('下载已取消', 'info');
                    } else {
                        showToast(result.data?.reason || '取消失败', 'warning');
                    }
                    this.refreshDownloadList();
                } catch (e) { showToast(`取消失败: ${e.message}`, 'error'); }
            },
            async retryDownload(taskId) {
                try {
                    const result = await adminFetch(`/api/model-switch/download/${taskId}/retry`, { method: 'POST' });
                    if (result.data?.success || result.success) {
                        showToast('重试下载已启动', 'success');
                        this.startDownloadPolling();
                    } else {
                        showToast(result.data?.reason || '重试失败', 'error');
                    }
                } catch (e) { showToast(`重试失败: ${e.message}`, 'error'); }
            },
        },
        health: {
            async refresh() {
                try {
                    const [alertData, detailData, historyData] = await Promise.all([
                        adminFetch('/api/health'),
                        adminFetch('/api/health/detailed'),
                        adminFetch('/api/health/history')
                    ]);
                    this.renderBanner(alertData);
                    this.renderDetails(detailData);
                    this.renderHistory(historyData);
                } catch (e) {
                    const bannerEl = document.getElementById('aios-health-banner');
                    const detailsEl = document.getElementById('aios-health-details');
                    const historyEl = document.getElementById('aios-health-history');
                    if (bannerEl) bannerEl.innerHTML = errorHTML(e.message);
                    if (detailsEl) detailsEl.innerHTML = errorHTML(e.message);
                    if (historyEl) historyEl.innerHTML = errorHTML(e.message);
                }
            },
            renderBanner(data) {
                const payload = data.data || data || {};
                const status = payload.status || payload.scores?.status || 'unknown';
                const score = payload.health_score ?? payload.scores?.overall ?? '-';
                const currentModel = payload.current_model || payload.models?.current_model || '-';
                const reasons = payload.alert_reasons || payload.scores?.alerts?.map(item => item.message).filter(Boolean) || [];
                const scoreText = typeof score === 'number' ? `${score}` : score;
                const el = document.getElementById('aios-health-banner');
                if (el) {
                    el.innerHTML = `
                        <div class="aios-p-banner-title">系统健康状态</div>
                        <div class="aios-p-banner-cards">
                            <div class="aios-p-banner-item"><div class="aios-p-banner-icon"><i class="fas fa-heartbeat"></i></div><div class="aios-p-banner-info"><div class="aios-p-banner-label">状态</div><div class="aios-p-banner-value aios-p-value-active">${escapeHtml(status)}</div></div></div>
                            <div class="aios-p-banner-item"><div class="aios-p-banner-icon"><i class="fas fa-medal"></i></div><div class="aios-p-banner-info"><div class="aios-p-banner-label">健康分</div><div class="aios-p-banner-value">${escapeHtml(scoreText)}</div></div></div>
                            <div class="aios-p-banner-item"><div class="aios-p-banner-icon"><i class="fas fa-cube"></i></div><div class="aios-p-banner-info"><div class="aios-p-banner-label">当前模型</div><div class="aios-p-banner-value">${escapeHtml(currentModel)}</div></div></div>
                        </div>
                        ${reasons.length ? `<div style="margin-top:var(--space-md);font-size:12px;color:var(--text-secondary);">${reasons.map(item => `<div>• ${escapeHtml(item)}</div>`).join('')}</div>` : ''}
                    `;
                }
            },
            renderDetails(data) {
                const payload = data.data || data || {};
                const checks = payload.checks || {};
                const engines = payload.engines || {};
                const models = payload.models || {};
                const cards = [
                    { icon: 'fa-microchip', label: 'GPU', value: checks.gpu?.available === false ? '不可用' : `${checks.gpu?.utilization ?? payload.gpu?.utilization ?? 0}%` },
                    { icon: 'fa-server', label: 'Go后端', value: checks.go_backend?.reachable === false ? '异常' : '正常' },
                    { icon: 'fa-laptop-code', label: 'Python后端', value: checks.python_backend?.reachable === false ? '异常' : '正常' },
                    { icon: 'fa-database', label: 'Redis', value: checks.redis?.available === false || payload.redis === false ? '异常' : '正常' },
                ];
                const engineRows = Object.entries(engines).map(([name, value]) => `<tr><td>${escapeHtml(name)}</td><td>${value?.running ? '运行中' : '未运行'}</td><td>${escapeHtml(value?.port ?? '-')}</td></tr>`);
                const modelRows = Object.entries(models).map(([name, value]) => `<tr><td>${escapeHtml(name)}</td><td>${value?.running ? '运行中' : '未运行'}</td><td>${escapeHtml(value?.active_requests ?? '-')}</td></tr>`);
                const el = document.getElementById('aios-health-details');
                if (el) {
                    el.innerHTML = `
                        <div class="aios-p-stats-grid">${cards.map(c => `<div class="aios-p-stat-card"><div class="aios-p-stat-icon"><i class="fas ${c.icon}"></i></div><div class="aios-p-stat-body"><div class="aios-p-stat-label">${c.label}</div><div class="aios-p-stat-value">${c.value}</div></div></div>`).join('')}</div>
                        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:var(--space-lg);margin-top:var(--space-lg);">
                            <div>
                                <div style="font-size:13px;font-weight:600;color:var(--text-primary);margin-bottom:8px;">引擎状态</div>
                                ${engineRows.length ? `<table class="aios-p-table"><thead><tr><th>引擎</th><th>状态</th><th>端口</th></tr></thead><tbody>${engineRows.join('')}</tbody></table>` : emptyHTML('暂无引擎数据')}
                            </div>
                            <div>
                                <div style="font-size:13px;font-weight:600;color:var(--text-primary);margin-bottom:8px;">模型状态</div>
                                ${modelRows.length ? `<table class="aios-p-table"><thead><tr><th>模型</th><th>状态</th><th>请求数</th></tr></thead><tbody>${modelRows.join('')}</tbody></table>` : emptyHTML('暂无模型数据')}
                            </div>
                        </div>
                    `;
                }
            },
            renderHistory(data) {
                const payload = data.data || data || [];
                const list = Array.isArray(payload) ? payload.slice(0, 10) : [];
                const el = document.getElementById('aios-health-history');
                if (!el) return;
                if (!list.length) {
                    el.innerHTML = emptyHTML('暂无健康历史');
                    return;
                }
                el.innerHTML = `<div style="display:flex;flex-direction:column;gap:var(--space-sm);">${list.map(item => {
                    const score = item.health_score ?? item.score ?? item.scores?.overall ?? '-';
                    const status = item.status ?? item.scores?.status ?? '-';
                    const ts = item.timestamp ?? item.time ?? '-';
                    return `<div class="aios-p-banner-item"><div class="aios-p-banner-info"><div class="aios-p-banner-label">${escapeHtml(ts)}</div><div style="font-size:12px;color:var(--text-secondary);">状态: ${escapeHtml(status)} • 分数: ${escapeHtml(score)}</div></div></div>`;
                }).join('')}</div>`;
            },
        },
        ratelimit: {
            async refresh() {
                try {
                    const [configData, statsData] = await Promise.all([
                        adminFetch('/api/ratelimit/config'),
                        adminFetch('/api/ratelimit/stats')
                    ]);
                    this.renderStats(statsData);
                    this.fillForm(configData.data || configData || {});
                } catch (e) {
                    const el = document.getElementById('aios-ratelimit-stats');
                    if (el) el.innerHTML = errorHTML(e.message);
                }
            },
            renderStats(data) {
                const payload = data.data || data || {};
                const cards = [
                    { icon: 'fa-plug', label: '当前并发', value: payload.current_concurrency ?? payload.current_requests ?? 0 },
                    { icon: 'fa-list', label: '队列长度', value: payload.queue_length ?? payload.waiting_requests ?? 0 },
                    { icon: 'fa-ban', label: '已限流请求', value: payload.rate_limited_requests ?? payload.rejected_requests ?? 0 },
                    { icon: 'fa-tasks', label: '总请求数', value: payload.total_requests ?? '-' },
                ];
                const el = document.getElementById('aios-ratelimit-stats');
                if (el) {
                    el.innerHTML = cards.map(c => `<div class="aios-p-stat-card"><div class="aios-p-stat-icon"><i class="fas ${c.icon}"></i></div><div class="aios-p-stat-body"><div class="aios-p-stat-label">${c.label}</div><div class="aios-p-stat-value">${c.value}</div></div></div>`).join('');
                }
            },
            fillForm(config) {
                document.getElementById('aios-rl-ip-limit').value = config.ip_qps_limit ?? config.limit_per_window ?? 100;
                document.getElementById('aios-rl-window').value = config.ip_qps_window_seconds ?? config.window_seconds ?? 60;
                document.getElementById('aios-rl-concurrency').value = config.concurrency_limit ?? config.max_concurrency ?? 8;
                document.getElementById('aios-rl-stream-concurrency').value = config.max_stream_concurrent ?? config.stream_concurrency_limit ?? '';
                document.getElementById('aios-rl-timeout').value = config.queue_timeout_seconds ?? config.wait_timeout_seconds ?? 30;
                document.getElementById('aios-rl-max-queue').value = config.max_queue_size ?? '';
                document.getElementById('aios-rl-token-limit').value = config.token_limit_per_minute ?? config.input_token_limit_per_minute ?? '';
                document.getElementById('aios-rl-max-model-len').value = config.max_model_len ?? '';
                document.getElementById('aios-rl-whitelist').value = (config.whitelist_ips || []).join(',');
                document.getElementById('aios-rl-paths').value = (config.rate_limited_paths || []).join(',');
            },
            async save() {
                const payload = {
                    ip_qps_limit: Number(document.getElementById('aios-rl-ip-limit').value || 100),
                    ip_qps_window_seconds: Number(document.getElementById('aios-rl-window').value || 60),
                    concurrency_limit: Number(document.getElementById('aios-rl-concurrency').value || 8),
                    queue_timeout_seconds: Number(document.getElementById('aios-rl-timeout').value || 30),
                    whitelist_ips: document.getElementById('aios-rl-whitelist').value.split(',').map(item => item.trim()).filter(Boolean),
                    rate_limited_paths: document.getElementById('aios-rl-paths').value.split(',').map(item => item.trim()).filter(Boolean),
                };
                const streamLimit = Number(document.getElementById('aios-rl-stream-concurrency').value || 0);
                const maxQueue = Number(document.getElementById('aios-rl-max-queue').value || 0);
                const tokenLimit = Number(document.getElementById('aios-rl-token-limit').value || 0);
                const maxModelLen = Number(document.getElementById('aios-rl-max-model-len').value || 0);
                if (streamLimit > 0) payload.max_stream_concurrent = streamLimit;
                if (maxQueue > 0) payload.max_queue_size = maxQueue;
                if (tokenLimit > 0) payload.token_limit_per_minute = tokenLimit;
                if (maxModelLen > 0) payload.max_model_len = maxModelLen;
                try {
                    await adminFetch('/api/ratelimit/config', { method: 'PUT', body: JSON.stringify(payload) });
                    showToast('限流配置已保存', 'success');
                    this.refresh();
                } catch (e) {
                    showToast(`保存失败: ${e.message}`, 'error');
                }
            },
            async refresh() {
                try {
                    const result = await adminFetch('/api/ratelimit/config');
                    const config = result.data || result || {};
                    const ipLimit = document.getElementById('aios-rl-ip-limit');
                const windowEl = document.getElementById('aios-rl-window');
                const concurrency = document.getElementById('aios-rl-concurrency');
                const timeoutEl = document.getElementById('aios-rl-timeout');
                const whitelist = document.getElementById('aios-rl-whitelist');
                const paths = document.getElementById('aios-rl-paths');
                
                if (ipLimit) ipLimit.value = config.ip_qps_limit ?? config.limit_per_window ?? 100;
                if (windowEl) windowEl.value = config.ip_qps_window_seconds ?? config.window_seconds ?? 60;
                if (concurrency) concurrency.value = config.concurrency_limit ?? config.max_concurrency ?? 8;
                if (timeoutEl) timeoutEl.value = config.queue_timeout_seconds ?? config.wait_timeout_seconds ?? 30;
                if (whitelist) whitelist.value = (config.whitelist_ips || []).join(',');
                if (paths) paths.value = (config.rate_limited_paths || []).join(',');
                } catch (e) {
                    const el = document.getElementById('aios-ratelimit-stats');
                    if (el) el.innerHTML = errorHTML(e.message);
                }
            },
        },
        config: {
            async refresh() {
                try {
                    const [result, logResult] = await Promise.all([
                        adminFetch('/api/config'),
                        adminFetch('/api/config/operation-log').catch(() => ({ items: [] }))
                    ]);
                    const payload = result.data || result || {};
                    const editor = document.getElementById('aios-config-editor');
                    if (editor) editor.value = JSON.stringify(payload, null, 2);
                    this.renderOperationLog(logResult);
                } catch (e) {
                    const editor = document.getElementById('aios-config-editor');
                    if (editor) editor.value = '';
                    showToast(`加载配置失败: ${e.message}`, 'error');
                }
            },
            renderOperationLog(data) {
                const el = document.getElementById('aios-config-operation-log');
                if (!el) return;
                const items = data.items || data.data?.items || [];
                if (!items.length) {
                    el.innerHTML = emptyHTML('暂无操作日志');
                    return;
                }
                el.innerHTML = `<div style="display:flex;flex-direction:column;gap:var(--space-sm);">${items.slice(0, 20).map(item => `
                    <div class="aios-p-banner-item">
                        <div class="aios-p-banner-info">
                            <div class="aios-p-banner-label">${escapeHtml(item.timestamp || '-')} · ${escapeHtml(item.operator || '-')}</div>
                            <div style="font-size:12px;color:var(--text-secondary);">动作: ${escapeHtml(item.action || '-')} · 版本: ${escapeHtml(item.version_before ?? '-')} → ${escapeHtml(item.version_after ?? '-')}</div>
                        </div>
                    </div>`).join('')}</div>`;
            },
            async save() {
                try {
                    const editor = document.getElementById('aios-config-editor');
                    if (!editor) return;
                    let payload;
                    try {
                        payload = JSON.parse(editor.value || '{}');
                    } catch {
                        showToast('配置 JSON 格式无效', 'warning');
                        return;
                    }
                    const result = await adminFetch('/api/config', { method: 'PUT', body: JSON.stringify(payload) });
                    if (result.detail?.error === 'version conflict' || result.detail?.current_version) {
                        showToast(`配置版本冲突，请刷新后重试（当前版本 ${result.detail.current_version}）`, 'warning');
                        return;
                    }
                    showToast('配置已保存', 'success');
                    this.refresh();
                } catch (e) {
                    showToast(`保存失败: ${e.message}`, 'error');
                }
            },
            async reload() {
                try {
                    const result = await adminFetch('/api/config/reload', { method: 'POST' });
                    if (result.detail) {
                        showToast(`重载失败: ${typeof result.detail === 'string' ? result.detail : JSON.stringify(result.detail)}`, 'error');
                        return;
                    }
                    showToast('配置已重载', 'success');
                    this.refresh();
                } catch (e) {
                    showToast(`重载失败: ${e.message}`, 'error');
                }
            },
        },
    };

    let refreshTimer = null;
    function startAutoRefresh() {
        if (refreshTimer) clearInterval(refreshTimer);
        refreshTimer = setInterval(() => {
            try {
                const gpuVisible = document.getElementById('section-aios-gpu');
                const modelVisible = document.getElementById('section-aios-model');
                const healthVisible = document.getElementById('section-aios-health');
                const rateLimitVisible = document.getElementById('section-aios-ratelimit');
                const configVisible = document.getElementById('section-aios-config');
                
                if (gpuVisible && gpuVisible.classList.contains('active')) {
                    window.AiosManager.gpu.refresh();
                }
                if (modelVisible && modelVisible.classList.contains('active')) {
                    window.AiosManager.model.refresh();
                }
                if (healthVisible && healthVisible.classList.contains('active')) {
                    window.AiosManager.health.refresh();
                }
                if (rateLimitVisible && rateLimitVisible.classList.contains('active')) {
                    window.AiosManager.ratelimit.refresh();
                }
                if (configVisible && configVisible.classList.contains('active')) {
                    window.AiosManager.config.refresh();
                }
            } catch (e) {}
        }, 5000);
    }

    waitForDOM((nav, content) => {
        injectUI(nav, content);
        AiosManager.model.initRealtime();
        startMenuWatcher(nav, content);
        startAutoRefresh();
    });
})();
