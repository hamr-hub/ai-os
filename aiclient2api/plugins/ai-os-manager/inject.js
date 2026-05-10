(function() {
    const CSS_LINK = '<link rel="stylesheet" href="/plugins/ai-os-manager/styles.css">';
    const TOAST_CONTAINER = '<div class="aios-toast-container" id="aios-toast-container"></div>';

    function showTokenModal() {
        return new Promise((resolve) => {
            const overlay = document.createElement('div');
            overlay.className = 'aios-p-modal-overlay';

            const modal = document.createElement('div');
            modal.className = 'aios-p-modal';

            const header = document.createElement('div');
            header.className = 'aios-p-modal-header';
            header.textContent = '管理员验证:';

            const input = document.createElement('input');
            input.className = 'aios-p-input';
            input.type = 'password';
            input.placeholder = '请输入 Admin Token';
            input.style.width = '100%';

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
            modal.appendChild(input);
            modal.appendChild(actions);
            overlay.appendChild(modal);
            document.body.appendChild(overlay);

            input.focus();
            const cleanup = (value) => { overlay.remove(); resolve(value); };
            cancelBtn.onclick = () => cleanup(null);
            submitBtn.onclick = () => cleanup(input.value || null);
            input.onkeydown = (e) => {
                if (e.key === 'Enter') cleanup(input.value || null);
                if (e.key === 'Escape') cleanup(null);
            };
        });
    }

    function adminFetch(url, options = {}) {
        const token = localStorage.getItem('aios_admin_token') || '';
        const headers = { 'Content-Type': 'application/json', ...options.headers };
        if (token) headers['X-Admin-Token'] = token;
        return fetch(url, { ...options, headers }).then(r => {
            if (r.status === 401) {
                return showTokenModal().then(newToken => {
                    if (newToken) { localStorage.setItem('aios_admin_token', newToken); return adminFetch(url, options); }
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
        toast.innerHTML = `<span>${message}</span><button class="aios-toast-close" onclick="this.parentElement.remove()">&times;</button>`;
        container.appendChild(toast);
        setTimeout(() => toast.remove(), 4000);
    }

    function loadingHTML(text = '加载中...') {
        return `<div class="aios-p-loading">${text}</div>`;
    }

    function emptyHTML(text = '暂无数据') {
        return `<div class="aios-p-empty"><i class="fas fa-inbox"></i><span>${text}</span></div>`;
    }

    function errorHTML(msg) {
        return `<div class="aios-p-error">${msg}</div>`;
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

    function drawMiniChart(canvasId, dataPoints, maxLen) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const w = canvas.parentElement.clientWidth || 200;
        const h = 50;
        canvas.width = w;
        canvas.height = h;
        const points = dataPoints.slice(-maxLen);
        if (points.length < 2) return;
        const max = Math.max(...points, 1);
        ctx.clearRect(0, 0, w, h);
        ctx.beginPath();
        ctx.strokeStyle = '#818cf8';
        ctx.lineWidth = 1.5;
        points.forEach((v, i) => {
            const x = (i / (points.length - 1)) * w;
            const y = h - (v / max) * (h - 4) - 2;
            i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        });
        ctx.stroke();
        ctx.lineTo(w, h);
        ctx.lineTo(0, h);
        ctx.closePath();
        ctx.fillStyle = 'rgba(99, 102, 241, 0.08)';
        ctx.fill();
    }

    const GPU_HTML = `
<div class="section" id="section-aios-gpu" style="display:none;">
    <div class="section-header">
        <h2><i class="fas fa-microchip"></i> GPU 监控</h2>
        <div class="section-actions">
            <button class="aios-p-btn aios-p-btn-sm" onclick="AiosManager.gpu.refresh()"><i class="fas fa-sync-alt"></i> 刷新</button>
        </div>
    </div>
    <div class="aios-p-stats-grid" id="aios-gpu-stats">${loadingHTML()}</div>
    <div class="aios-p-card aios-p-chart-card" style="margin-top:var(--space-lg);">
        <div class="aios-p-card-header"><h3><i class="fas fa-chart-area"></i> GPU 历史趋势</h3></div>
        <div class="aios-p-card-content"><canvas id="aios-gpu-chart" style="height:80px;"></canvas></div>
    </div>
    <div class="aios-p-card aios-p-status-card" style="margin-top:var(--space-lg);">
        <div class="aios-p-card-header"><h3><i class="fas fa-bolt"></i> 引擎状态</h3></div>
        <div class="aios-p-card-content" id="aios-engine-status">${loadingHTML()}</div>
    </div>
</div>`;

    const MODEL_HTML = `
<div class="section" id="section-aios-model" style="display:none;">
    <div class="section-header">
        <h2><i class="fas fa-cubes"></i> 模型管理</h2>
        <div class="section-actions">
            <button class="aios-p-btn aios-p-btn-sm" onclick="AiosManager.model.refresh()"><i class="fas fa-sync-alt"></i> 刷新</button>
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
                    <button class="aios-p-btn aios-p-btn-primary" onclick="AiosManager.model.switchModel()"><i class="fas fa-play"></i> 切换</button>
                </div>
            </div>
            <div id="aios-switch-status" style="margin-top:var(--space-md);"></div>
        </div>
    </div>
    <div class="aios-p-models-shell" style="margin-top:var(--space-lg);">
        <div id="aios-model-list">${loadingHTML()}</div>
    </div>
    <div class="aios-p-card aios-p-action-card" style="margin-top:var(--space-lg);">
        <div class="aios-p-card-header"><h3><i class="fas fa-download"></i> 模型下载</h3></div>
        <div class="aios-p-card-content">
            <div class="aios-p-form-grid">
                <div class="aios-p-form-group" style="flex:2;">
                    <label>模型ID (HuggingFace / ModelScope)</label>
                    <input id="aios-download-model-name" class="aios-p-input" placeholder="如: Qwen/Qwen2.5-7B-Instruct" style="width:100%;">
                </div>
                <div class="aios-p-form-group">
                    <label>来源</label>
                    <select id="aios-download-source" class="aios-p-input aios-p-select">
                        <option value="hf">HuggingFace</option>
                        <option value="ms">ModelScope</option>
                    </select>
                </div>
                <div class="aios-p-form-actions">
                    <button class="aios-p-btn aios-p-btn-primary" onclick="AiosManager.model.download()"><i class="fas fa-cloud-download-alt"></i> 下载</button>
                </div>
            </div>
            <div id="aios-download-tasks" style="margin-top:var(--space-lg);"></div>
        </div>
    </div>
</div>`;

    const HEALTH_HTML = `
<div class="section" id="section-aios-health" style="display:none;">
    <div class="section-header">
        <h2><i class="fas fa-heartbeat"></i> 健康运维</h2>
        <div class="section-actions">
            <button class="aios-p-btn aios-p-btn-sm" onclick="AiosManager.health.refresh()"><i class="fas fa-sync-alt"></i> 刷新</button>
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
<div class="section" id="section-aios-ratelimit" style="display:none;">
    <div class="section-header">
        <h2><i class="fas fa-tachometer-alt"></i> 限流控制</h2>
        <div class="section-actions">
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
                    <label>排队超时(秒)</label>
                    <input id="aios-rl-timeout" class="aios-p-input" type="number" min="1">
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
<div class="section" id="section-aios-config" style="display:none;">
    <div class="section-header">
        <h2><i class="fas fa-cog"></i> 配置中心</h2>
        <div class="section-actions">
            <button class="aios-p-btn aios-p-btn-sm" onclick="AiosManager.config.refresh()"><i class="fas fa-sync-alt"></i> 刷新</button>
            <button class="aios-p-btn aios-p-btn-sm aios-p-btn-primary" onclick="AiosManager.config.save()"><i class="fas fa-save"></i> 保存</button>
        </div>
    </div>
    <div class="aios-p-card">
        <div class="aios-p-card-header"><h3><i class="fas fa-file-code"></i> 当前配置</h3></div>
        <div class="aios-p-card-content">
            <textarea id="aios-config-editor" class="aios-p-input" style="min-height:360px;font-family:Menlo,monospace;resize:vertical;"></textarea>
        </div>
    </div>
</div>`;

    function waitForDOM(cb) {
        const container = document.querySelector('.sidebar-nav') || document.querySelector('#sidebar');
        const content = document.querySelector('#content-container') || document.querySelector('#content');
        if (container && content) { cb(container, content); return; }
        let tries = 0;
        const timer = setInterval(() => {
            tries++;
            const c = document.querySelector('.sidebar-nav') || document.querySelector('#sidebar');
            const ct = document.querySelector('#content-container') || document.querySelector('#content');
            if (c && ct) { clearInterval(timer); cb(c, ct); }
            else if (tries > 60) clearInterval(timer);
        }, 500);
    }

    function injectUI(navContainer, contentContainer) {
        if (!document.querySelector('link[href="/plugins/ai-os-manager/styles.css"]')) {
            document.head.insertAdjacentHTML('beforeend', CSS_LINK);
        }
        if (!document.getElementById('aios-toast-container')) {
            document.body.insertAdjacentHTML('beforeend', TOAST_CONTAINER);
        }
        const divider = navContainer.querySelector('.nav-divider');
        const dividerHTML = '<div class="nav-divider"></div>';
        const menuItems = [
            '<a class="nav-item" id="nav-aios-gpu" href="#" onclick="return false;"><i class="fas fa-microchip"></i> GPU监控</a>',
            '<a class="nav-item" id="nav-aios-model" href="#" onclick="return false;"><i class="fas fa-cubes"></i> 模型管理</a>',
            '<a class="nav-item" id="nav-aios-health" href="#" onclick="return false;"><i class="fas fa-heartbeat"></i> 健康运维</a>',
            '<a class="nav-item" id="nav-aios-ratelimit" href="#" onclick="return false;"><i class="fas fa-tachometer-alt"></i> 限流控制</a>',
            '<a class="nav-item" id="nav-aios-config" href="#" onclick="return false;"><i class="fas fa-cog"></i> 配置中心</a>',
        ];
        const menuHTML = dividerHTML + menuItems.join('');
        if (divider) {
            divider.insertAdjacentHTML('afterend', menuHTML);
        } else {
            navContainer.insertAdjacentHTML('beforeend', menuHTML);
        }
        const aiosScope = document.createElement('div');
        aiosScope.className = 'aios-p-scope';
        contentContainer.appendChild(aiosScope);
        aiosScope.insertAdjacentHTML('beforeend', GPU_HTML);
        aiosScope.insertAdjacentHTML('beforeend', MODEL_HTML);
        aiosScope.insertAdjacentHTML('beforeend', HEALTH_HTML);
        aiosScope.insertAdjacentHTML('beforeend', RATELIMIT_HTML);
        aiosScope.insertAdjacentHTML('beforeend', CONFIG_HTML);
        document.getElementById('nav-aios-gpu').addEventListener('click', (e) => {
            e.preventDefault(); showSection('aios-gpu'); AiosManager.gpu.refresh();
        });
        document.getElementById('nav-aios-model').addEventListener('click', (e) => {
            e.preventDefault(); showSection('aios-model'); AiosManager.model.refresh();
        });
        document.getElementById('nav-aios-health').addEventListener('click', (e) => {
            e.preventDefault(); showSection('aios-health'); AiosManager.health.refresh();
        });
        document.getElementById('nav-aios-ratelimit').addEventListener('click', (e) => {
            e.preventDefault(); showSection('aios-ratelimit'); AiosManager.ratelimit.refresh();
        });
        document.getElementById('nav-aios-config').addEventListener('click', (e) => {
            e.preventDefault(); showSection('aios-config'); AiosManager.config.refresh();
        });
        AiosManager.gpu.refresh();
    }

    function showSection(id) {
        document.querySelectorAll('.section').forEach(s => s.style.display = 'none');
        const el = document.getElementById(`section-${id}`);
        if (el) el.style.display = '';
        document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
        const nav = document.getElementById(`nav-${id}`);
        if (nav) nav.classList.add('active');
    }

    window.AiosManager = {
        gpu: {
            history: { utilization: [], memoryPct: [], temperature: [] },
            async refresh() {
                try {
                    const [gpuData, engineData] = await Promise.all([
                        adminFetch('/api/gpu-monitor/info'),
                        adminFetch('/api/engine/status')
                    ]);
                    this.renderGPUCards(gpuData);
                    this.renderEngineStatus(engineData);
                    this.updateHistory(gpuData);
                } catch (e) {
                    document.getElementById('aios-gpu-stats').innerHTML = errorHTML(e.message);
                }
            },
            renderGPUCards(data) {
                const gpuDataArr = data.data || [];
                const gpu = gpuDataArr[0];
                if (!gpu) {
                    document.getElementById('aios-gpu-stats').innerHTML = emptyHTML('未检测到 GPU');
                    return;
                }
                const util = gpu.gpuUtilization ?? 0;
                const memUsed = gpu.memoryUsed ?? 0;
                const memTotal = gpu.memoryTotal ?? 0;
                const memPct = memTotal > 0 ? (memUsed / memTotal * 100) : 0;
                const temp = gpu.temperature ?? 0;
                const power = gpu.powerDraw ?? 0;
                const cards = [
                    { icon: 'fa-tag', label: 'GPU', value: gpu.name || '-' },
                    { icon: 'fa-chart-line', label: '利用率', value: `${util}%`, progress: util, ptype: util > 80 ? 'danger' : util > 50 ? 'warning' : 'success' },
                    { icon: 'fa-memory', label: '显存', value: `${formatBytes(memUsed)} / ${formatBytes(memTotal)}`, progress: memPct, ptype: memPct > 80 ? 'danger' : 'success' },
                    { icon: 'fa-thermometer-half', label: '温度', value: `${temp}°C`, progress: temp, ptype: temp > 80 ? 'danger' : temp > 60 ? 'warning' : 'success' },
                    { icon: 'fa-plug', label: '功耗', value: `${power}W` },
                ];
                document.getElementById('aios-gpu-stats').innerHTML = cards.map(c => {
                    const prog = c.progress != null ? `<div class="aios-p-progress-bar"><div class="aios-p-progress-fill aios-${c.ptype}" style="width:${Math.min(c.progress, 100)}%"></div></div>` : '';
                    return `<div class="aios-p-stat-card"><div class="aios-p-stat-icon"><i class="fas ${c.icon}"></i></div><div class="aios-p-stat-body"><div class="aios-p-stat-label">${c.label}</div><div class="aios-p-stat-value">${c.value}</div>${prog}</div></div>`;
                }).join('');
            },
            renderEngineStatus(data) {
                const result = data.data || data;
                const raw = result.current || result;
                const services = raw.services || raw.engines || [];
                if (!services || services.length === 0) {
                    document.getElementById('aios-engine-status').innerHTML = emptyHTML('未检测到引擎');
                    return;
                }
                const engines = services.map(s => {
                    const engineType = s.engine_type || 'unknown';
                    const status = s.status || 'unknown';
                    const running = status === 'running';
                    const svcName = s.service_name || engineType;
                    const model = s.model || s.model_name || '-';
                    const port = s.port ?? '-';
                    const uptime = s.uptime_seconds ? `${Math.floor(s.uptime_seconds / 3600)}h${Math.floor((s.uptime_seconds % 3600) / 60)}m` : '-';
                    const health = s.health || 'unknown';
                    const pid = s.pid ?? null;
                    return { engineType, status, running, svcName, model, port, uptime, health, pid };
                });
                const html = `<div class="aios-p-engine-grid">${engines.map(e => `
                    <div class="aios-p-engine-card ${e.running ? 'aios-p-engine-running' : (e.status === 'not_found' ? 'aios-p-engine-stopped' : 'aios-p-engine-stopped')}" onclick="AiosManager.gpu.switchEngine('${e.engineType}')">
                        <div class="aios-p-engine-header">
                            <div class="aios-p-engine-icon"><i class="fas fa-bolt"></i></div>
                            <div class="aios-p-engine-title">${engineDisplayName(e.engineType)}</div>
                        </div>
                        <div class="aios-p-engine-status-text ${e.running ? 'aios-p-engine-running-text' : 'aios-p-engine-stopped-text'}">
                            ${e.running ? '运行中' : (e.status === 'not_found' ? '未安装' : '已停止')}
                        </div>
                        ${e.running ? `<div class="aios-p-engine-info"><div>模型: ${e.model}</div><div>端口: ${e.port}</div>${e.uptime !== '-' ? `<div>运行: ${e.uptime}</div>` : ''}${e.pid ? `<div>PID: ${e.pid}</div>` : ''}</div>` : ''}
                        <div style="margin-top:auto;padding-top:var(--space-sm);">
                            <button class="aios-p-btn aios-p-btn-sm ${e.running ? 'aios-p-btn-success' : ''}" style="width:100%;">
                                <i class="fas ${e.running ? 'fa-check-circle' : 'fa-play'}"></i> ${e.running ? '当前引擎' : '切换到此引擎'}
                            </button>
                        </div>
                    </div>`).join('')}</div>`;
                document.getElementById('aios-engine-status').innerHTML = html;
            },
            async switchEngine(engineType) {
                try {
                    let modelName = '';
                    const aggResult = await adminFetch('/api/model-switch/aggregated');
                    const aggData = aggResult.data || aggResult;
                    const groups = aggData.groups || [];
                    for (const g of groups) {
                        for (const v of (g.variants || [])) {
                            if (v.running || v.is_current) { modelName = v.name || g.base_name; break; }
                        }
                        if (modelName) break;
                    }
                    if (!modelName && groups.length > 0) modelName = groups[0].base_name;
                    if (!modelName) { showToast('没有可用模型，请先下载模型', 'warning'); return; }
                    const result = await adminFetch('/api/engine/switch', {
                        method: 'POST',
                        body: JSON.stringify({ model_name: modelName, engine_type: normalizeEngineType(engineType), port: 8000 })
                    });
                    if (result.success || result.data?.success) {
                        showToast(`切换引擎到 ${engineDisplayName(engineType)} 成功`, 'success');
                    } else {
                        const reason = result.reason || result.error || '未知错误';
                        if (reason === 'insufficient_gpu_memory') {
                            showToast(`GPU显存不足: ${result.suggestion || ''}`, 'error');
                        } else if (reason === 'already_running_same_engine') {
                            showToast(`${engineDisplayName(engineType)} 已是当前引擎`, 'info');
                        } else {
                            showToast(`切换引擎失败: ${reason}`, 'error');
                        }
                    }
                    this.refresh();
                    AiosManager.model.refresh();
                } catch (e) {
                    showToast(`切换引擎失败: ${e.message}`, 'error');
                }
            },
            updateHistory(data) {
                const gpuDataArr = data.data || [];
                const gpu = gpuDataArr[0];
                if (!gpu) return;
                this.history.utilization.push(gpu.gpuUtilization ?? 0);
                this.history.memoryPct.push(gpu.memoryUsagePercent ?? 0);
                this.history.temperature.push(gpu.temperature ?? 0);
                const maxLen = 30;
                for (const k in this.history) {
                    if (this.history[k].length > maxLen) this.history[k] = this.history[k].slice(-maxLen);
                }
                drawMiniChart('aios-gpu-chart', this.history.utilization, maxLen);
            },
        },
        model: {
            _downloadPolling: null,
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
                } catch (e) {
                    document.getElementById('aios-model-banner').innerHTML = errorHTML(e.message);
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
                const modelDisplay = currentModel || '-';
                const engineDisplay = engineDisplayName(currentEngine);
                document.getElementById('aios-model-banner').innerHTML = `
                    <div class="aios-p-banner-title">当前运行状态</div>
                    <div class="aios-p-banner-cards">
                        <div class="aios-p-banner-item"><div class="aios-p-banner-icon"><i class="fas fa-bolt"></i></div><div class="aios-p-banner-info"><div class="aios-p-banner-label">引擎</div><div class="aios-p-banner-value aios-p-value-active">${engineDisplay}</div></div></div>
                        <div class="aios-p-banner-item"><div class="aios-p-banner-icon"><i class="fas fa-cube"></i></div><div class="aios-p-banner-info"><div class="aios-p-banner-label">模型</div><div class="aios-p-banner-value aios-p-value-active">${modelDisplay}</div></div></div>
                        <div class="aios-p-banner-item"><div class="aios-p-banner-icon"><i class="fas fa-hashtag"></i></div><div class="aios-p-banner-info"><div class="aios-p-banner-label">端口</div><div class="aios-p-banner-value">${currentPort}</div></div></div>
                    </div>`;
            },
            renderSwitchingStatus(switchData) {
                const data = switchData.data || switchData;
                const el = document.getElementById('aios-p-switching-banner');
                if (!el) return;
                const isSwitching = data.is_switching ?? false;
                const session = data.session || null;
                if (isSwitching && session) {
                    const progress = session.overall_progress ?? 0;
                    const target = session.target_model || '-';
                    const phasesHtml = (session.phases || []).map(p => {
                        const statusIcon = p.status === 'running' ? 'fa-spinner fa-spin' : p.status === 'success' ? 'fa-check' : p.status === 'failed' ? 'fa-times' : 'fa-clock';
                        return `<div style="display:flex;align-items:center;gap:8px;padding:4px 0;"><i class="fas ${statusIcon}" style="width:16px;"></i><span style="font-size:12px;color:var(--text-secondary);">${p.name}</span></div>`;
                    }).join('');
                    el.innerHTML = `<div class="aios-p-status-banner" style="border-color:rgba(var(--color-warning-rgb),0.3);">
                        <div class="aios-p-banner-title" style="color:var(--color-warning);">正在${session.action === 'switch' ? '切换' : session.action === 'start' ? '启动' : '停止'}模型</div>
                        <div style="display:flex;align-items:center;gap:var(--space-lg);">
                            <div style="flex:1;"><div style="font-size:14px;font-weight:600;color:var(--text-primary);">${target}</div><div style="margin-top:8px;">${phasesHtml}</div></div>
                            <div style="width:100px;"><div class="aios-p-progress-bar" style="height:8px;"><div class="aios-p-progress-fill aios-p-warning" style="width:${progress}%"></div></div><div style="font-size:11px;color:var(--text-muted);text-align:center;margin-top:4px;">${progress}%</div></div>
                        </div>
                        <div style="margin-top:var(--space-md);"><button class="aios-p-btn aios-p-btn-sm aios-p-btn-danger" onclick="AiosManager.model.cancelSwitch()"><i class="fas fa-times"></i> 取消</button></div>
                    </div>`;
                } else {
                    el.innerHTML = '';
                }
            },
            populateModelSelect(aggData) {
                const aggResult = aggData.data || aggData;
                const groups = aggResult.groups || [];
                const select = document.getElementById('aios-switch-model');
                if (!select) return;
                const currentModel = aggResult.current_model || '';
                select.innerHTML = groups.map(g => {
                    const selected = (g.base_name === currentModel || (g.variants && g.variants.some(v => v.is_current))) ? ' selected' : '';
                    return `<option value="${g.base_name}"${selected}>${g.base_name} (${g.variant_count || (g.variants || []).length}个变体)</option>`;
                }).join('');
            },
            populateEngineSelect(engineData) {
                const result = engineData.data || engineData;
                const raw = result.current || result;
                const services = raw.services || raw.engines || [];
                const select = document.getElementById('aios-switch-engine');
                if (!select) return;
                const engineTypes = ['vllm', 'sglang', 'llamacpp'];
                select.innerHTML = engineTypes.map(t => {
                    const running = services.find(s => normalizeEngineType(s.engine_type) === t && s.status === 'running');
                    return `<option value="${t}"${running ? ' selected' : ''}>${engineDisplayName(t)}</option>`;
                }).join('');
            },
            renderModelList(aggData) {
                const aggResult = aggData.data || aggData;
                const groups = aggResult.groups || [];
                if (!groups || groups.length === 0) {
                    document.getElementById('aios-model-list').innerHTML = emptyHTML('暂无模型，请通过模型下载添加');
                    return;
                }
                const html = `<div class="aios-p-models-list">${groups.map(g => {
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
                            return `<div class="aios-p-model-item ${isCurrent ? 'aios-p-current-model' : ''}">
                                <div class="aios-p-model-header">
                                    <div class="aios-p-model-title-wrap">
                                        <div class="aios-p-model-name">${vName}</div>
                                        <div class="aios-p-model-tags">
                                            <span class="aios-p-model-status ${isRunning ? 'aios-p-running' : 'aios-p-stopped'}">${isRunning ? '运行中' : (vPathExists ? '已下载' : '未下载')}</span>
                                            ${isCurrent ? '<span class="aios-p-badge aios-p-badge-primary">当前</span>' : ''}
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
                                    ${!vPathExists ? `<button class="aios-p-btn aios-p-btn-sm" onclick="AiosManager.model.downloadByName('${vName}')"><i class="fas fa-cloud-download-alt"></i> 下载</button>` : ''}
                                    ${vPathExists && !isRunning ? `<button class="aios-p-btn aios-p-btn-sm aios-p-btn-success" onclick="AiosManager.model.start('${vName}')"><i class="fas fa-play"></i> 启动</button>` : ''}
                                    ${isRunning && !isCurrent ? `<button class="aios-p-btn aios-p-btn-sm aios-p-btn-primary" onclick="AiosManager.model.switchTo('${vName}','${vEngine}')"><i class="fas fa-exchange-alt"></i> 切换</button>` : ''}
                                    ${isRunning ? `<button class="aios-p-btn aios-p-btn-sm aios-p-btn-danger" onclick="AiosManager.model.stop('${vName}')"><i class="fas fa-stop"></i> 停止</button>` : ''}
                                </div>
                            </div>`;
                        }).join('')}</div>
                    </div>`;
                }).join('')}</div>`;
                document.getElementById('aios-model-list').innerHTML = html;
            },
            async switchModel() {
                const modelName = document.getElementById('aios-switch-model').value;
                const engineType = document.getElementById('aios-switch-engine').value;
                const port = document.getElementById('aios-switch-port').value;
                if (!modelName) { showToast('请选择模型', 'warning'); return; }
                try {
                    const body = { modelName, engineType };
                    if (port) body.port = parseInt(port);
                    const result = await adminFetch('/api/model-switch/switch', {
                        method: 'POST', body: JSON.stringify(body)
                    });
                    const data = result.data || result;
                    if (data.taskId) {
                        showToast('切换任务已提交', 'info');
                        this.pollSwitchStatus();
                    } else if (data.success) {
                        showToast(`切换到 ${modelName} 成功`, 'success');
                        this.refresh();
                        AiosManager.gpu.refresh();
                    } else {
                        showToast(`切换失败: ${data.error || '未知错误'}`, 'error');
                    }
                } catch (e) {
                    showToast(`切换失败: ${e.message}`, 'error');
                }
            },
            async switchTo(modelName, backendType) {
                try {
                    const result = await adminFetch('/api/model-switch/switch', {
                        method: 'POST', body: JSON.stringify({ modelName, engineType: normalizeEngineType(backendType), async: true })
                    });
                    const data = result.data || result;
                    if (data.taskId) {
                        showToast('切换任务已提交', 'info');
                        this.pollSwitchStatus();
                    } else if (data.success) {
                        showToast(`切换到 ${modelName} 成功`, 'success');
                        this.refresh();
                        AiosManager.gpu.refresh();
                    } else {
                        showToast(`切换失败: ${data.error || '未知错误'}`, 'error');
                    }
                } catch (e) {
                    showToast(`切换失败: ${e.message}`, 'error');
                }
            },
            async start(modelName) {
                try {
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
                    const result = await adminFetch('/api/model-switch/stop', { method: 'POST', body: JSON.stringify({ modelName }) });
                    if (result.success || result.data?.success) {
                        showToast(`停止 ${modelName} 成功`, 'success');
                    } else {
                        showToast(`停止失败: ${result.error || result.data?.error || '未知错误'}`, 'error');
                    }
                    this.refresh();
                    AiosManager.gpu.refresh();
                } catch (e) { showToast(`停止失败: ${e.message}`, 'error'); }
            },
            async cancelSwitch() {
                try {
                    await adminFetch('/api/model-switch/cancel', { method: 'POST' });
                    showToast('已取消切换', 'info');
                    this.refresh();
                } catch (e) { showToast(`取消失败: ${e.message}`, 'error'); }
            },
            pollSwitchStatus() {
                setTimeout(() => this.refresh(), 3000);
            },
            async download() {
                const modelName = document.getElementById('aios-download-model-name').value.trim();
                const source = document.getElementById('aios-download-source').value;
                if (!modelName) { showToast('请输入模型ID', 'warning'); return; }
                try {
                    const result = await adminFetch('/api/model-switch/download', {
                        method: 'POST', body: JSON.stringify({ model_name: modelName, source })
                    });
                    const data = result.data || result;
                    if (data.task_id) {
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
                document.getElementById('aios-download-model-name').value = modelName;
                document.getElementById('aios-download-source').value = 'hf';
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
                            `<button class="aios-p-btn aios-p-btn-sm aios-p-btn-danger" onclick="AiosManager.model.cancelDownload('${t.task_id}')"><i class="fas fa-times"></i> 取消</button>` :
                            t.status === 'failed' ?
                            `<button class="aios-p-btn aios-p-btn-sm aios-p-btn-primary" onclick="AiosManager.model.retryDownload('${t.task_id}')"><i class="fas fa-redo"></i> 重试</button>` : '';
                        return `<div class="aios-p-banner-item" style="flex-wrap:wrap;">
                            <div class="aios-p-banner-info" style="flex:2;min-width:200px;">
                                <div class="aios-p-banner-label">${t.model_name || '-'} (${t.source || 'hf'})</div>
                                <div style="font-size:12px;color:${statusColor};font-weight:600;">${statusText}${speed > 0 ? ` | ${speed}MB/s | ETA ${etaStr}` : ''}${t.downloaded_bytes ? ` | ${downloaded}/${total}` : ''}</div>
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
                    document.getElementById('aios-health-banner').innerHTML = errorHTML(e.message);
                    document.getElementById('aios-health-details').innerHTML = errorHTML(e.message);
                    document.getElementById('aios-health-history').innerHTML = errorHTML(e.message);
                }
            },
            renderBanner(data) {
                const payload = data.data || data || {};
                const status = payload.status || payload.scores?.status || 'unknown';
                const score = payload.health_score ?? payload.scores?.overall ?? '-';
                const currentModel = payload.current_model || payload.models?.current_model || '-';
                const reasons = payload.alert_reasons || payload.scores?.alerts?.map(item => item.message).filter(Boolean) || [];
                const scoreText = typeof score === 'number' ? `${score}` : score;
                document.getElementById('aios-health-banner').innerHTML = `
                    <div class="aios-p-banner-title">系统健康状态</div>
                    <div class="aios-p-banner-cards">
                        <div class="aios-p-banner-item"><div class="aios-p-banner-icon"><i class="fas fa-heartbeat"></i></div><div class="aios-p-banner-info"><div class="aios-p-banner-label">状态</div><div class="aios-p-banner-value aios-p-value-active">${escapeHtml(status)}</div></div></div>
                        <div class="aios-p-banner-item"><div class="aios-p-banner-icon"><i class="fas fa-medal"></i></div><div class="aios-p-banner-info"><div class="aios-p-banner-label">健康分</div><div class="aios-p-banner-value">${escapeHtml(scoreText)}</div></div></div>
                        <div class="aios-p-banner-item"><div class="aios-p-banner-icon"><i class="fas fa-cube"></i></div><div class="aios-p-banner-info"><div class="aios-p-banner-label">当前模型</div><div class="aios-p-banner-value">${escapeHtml(currentModel)}</div></div></div>
                    </div>
                    ${reasons.length ? `<div style="margin-top:var(--space-md);font-size:12px;color:var(--text-secondary);">${reasons.map(item => `<div>• ${escapeHtml(item)}</div>`).join('')}</div>` : ''}`;
            },
            renderDetails(data) {
                const payload = data.data || data || {};
                const checks = payload.checks || {};
                const engines = payload.engines || {};
                const models = payload.models || {};
                const cards = [
                    { label: 'GPU', value: checks.gpu?.available === false ? '不可用' : `${checks.gpu?.utilization ?? payload.gpu?.utilization ?? 0}%` },
                    { label: 'Go后端', value: checks.go_backend?.reachable === false ? '异常' : '正常' },
                    { label: 'Python后端', value: checks.python_backend?.reachable === false ? '异常' : '正常' },
                    { label: 'Redis', value: checks.redis?.available === false || payload.redis === false ? '异常' : '正常' },
                ];
                const engineRows = Object.entries(engines).map(([name, value]) => `<tr><td>${escapeHtml(name)}</td><td>${value?.running ? '运行中' : '未运行'}</td><td>${escapeHtml(value?.port ?? '-')}</td></tr>`).join('');
                const modelRows = Object.entries(models).map(([name, value]) => `<tr><td>${escapeHtml(name)}</td><td>${value?.running ? '运行中' : '未运行'}</td><td>${escapeHtml(value?.active_requests ?? '-')}</td></tr>`).join('');
                document.getElementById('aios-health-details').innerHTML = `
                    <div class="aios-p-stats-grid">${cards.map(card => `<div class="aios-p-stat-card"><div class="aios-p-stat-body"><div class="aios-p-stat-label">${card.label}</div><div class="aios-p-stat-value">${card.value}</div></div></div>`).join('')}</div>
                    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:var(--space-lg);margin-top:var(--space-lg);">
                        <div>
                            <div style="font-size:13px;font-weight:600;color:var(--text-primary);margin-bottom:8px;">引擎状态</div>
                            ${engineRows ? `<table class="aios-p-table"><thead><tr><th>引擎</th><th>状态</th><th>端口</th></tr></thead><tbody>${engineRows}</tbody></table>` : emptyHTML('暂无引擎数据')}
                        </div>
                        <div>
                            <div style="font-size:13px;font-weight:600;color:var(--text-primary);margin-bottom:8px;">模型状态</div>
                            ${modelRows ? `<table class="aios-p-table"><thead><tr><th>模型</th><th>状态</th><th>请求数</th></tr></thead><tbody>${modelRows}</tbody></table>` : emptyHTML('暂无模型数据')}
                        </div>
                    </div>`;
            },
            renderHistory(data) {
                const payload = data.data || data || [];
                const list = Array.isArray(payload) ? payload.slice(0, 10) : [];
                if (!list.length) {
                    document.getElementById('aios-health-history').innerHTML = emptyHTML('暂无健康历史');
                    return;
                }
                document.getElementById('aios-health-history').innerHTML = `<div style="display:flex;flex-direction:column;gap:var(--space-sm);">${list.map(item => {
                    const score = item.health_score ?? item.score ?? item.scores?.overall ?? '-';
                    const status = item.status || item.scores?.status || '-';
                    const ts = item.timestamp || item.time || '-';
                    return `<div class="aios-p-banner-item"><div class="aios-p-banner-info"><div class="aios-p-banner-label">${escapeHtml(ts)}</div><div style="font-size:12px;color:var(--text-secondary);">状态: ${escapeHtml(status)} · 分数: ${escapeHtml(score)}</div></div></div>`;
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
                    document.getElementById('aios-ratelimit-stats').innerHTML = errorHTML(e.message);
                }
            },
            renderStats(data) {
                const payload = data.data || data || {};
                const cards = [
                    { label: '当前并发', value: payload.current_concurrency ?? payload.current_requests ?? 0 },
                    { label: '队列长度', value: payload.queue_length ?? payload.waiting_requests ?? 0 },
                    { label: '已限流请求', value: payload.rate_limited_requests ?? payload.rejected_requests ?? 0 },
                    { label: '总请求数', value: payload.total_requests ?? '-' },
                ];
                document.getElementById('aios-ratelimit-stats').innerHTML = cards.map(card => `<div class="aios-p-stat-card"><div class="aios-p-stat-body"><div class="aios-p-stat-label">${card.label}</div><div class="aios-p-stat-value">${card.value}</div></div></div>`).join('');
            },
            fillForm(config) {
                document.getElementById('aios-rl-ip-limit').value = config.ip_qps_limit ?? config.limit_per_window ?? 100;
                document.getElementById('aios-rl-window').value = config.ip_qps_window_seconds ?? config.window_seconds ?? 60;
                document.getElementById('aios-rl-concurrency').value = config.concurrency_limit ?? config.max_concurrency ?? 8;
                document.getElementById('aios-rl-timeout').value = config.queue_timeout_seconds ?? config.wait_timeout_seconds ?? 30;
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
                try {
                    await adminFetch('/api/ratelimit/config', { method: 'PUT', body: JSON.stringify(payload) });
                    showToast('限流配置已保存', 'success');
                    this.refresh();
                } catch (e) {
                    showToast(`保存失败: ${e.message}`, 'error');
                }
            },
        },
        config: {
            async refresh() {
                try {
                    const result = await adminFetch('/api/config');
                    const payload = result.data || result || {};
                    document.getElementById('aios-config-editor').value = JSON.stringify(payload, null, 2);
                } catch (e) {
                    document.getElementById('aios-config-editor').value = '';
                    showToast(`加载配置失败: ${e.message}`, 'error');
                }
            },
            async save() {
                const editor = document.getElementById('aios-config-editor');
                if (!editor) return;
                let payload;
                try {
                    payload = JSON.parse(editor.value || '{}');
                } catch (e) {
                    showToast('配置 JSON 格式无效', 'warning');
                    return;
                }
                try {
                    await adminFetch('/api/config', { method: 'PUT', body: JSON.stringify(payload) });
                    showToast('配置已保存', 'success');
                    this.refresh();
                } catch (e) {
                    showToast(`保存失败: ${e.message}`, 'error');
                }
            },
        },
    };

    let refreshTimer = null;
    function startAutoRefresh() {
        if (refreshTimer) clearInterval(refreshTimer);
        refreshTimer = setInterval(() => {
            const gpuVisible = document.getElementById('section-aios-gpu')?.style.display !== 'none';
            const modelVisible = document.getElementById('section-aios-model')?.style.display !== 'none';
            const healthVisible = document.getElementById('section-aios-health')?.style.display !== 'none';
            const rateLimitVisible = document.getElementById('section-aios-ratelimit')?.style.display !== 'none';
            const configVisible = document.getElementById('section-aios-config')?.style.display !== 'none';
            if (gpuVisible) AiosManager.gpu.refresh();
            if (modelVisible) AiosManager.model.refresh();
            if (healthVisible) AiosManager.health.refresh();
            if (rateLimitVisible) AiosManager.ratelimit.refresh();
            if (configVisible) AiosManager.config.refresh();
        }, 5000);
    }

    waitForDOM((nav, content) => {
        injectUI(nav, content);
        showSection('aios-gpu');
        startAutoRefresh();
    });
})();
