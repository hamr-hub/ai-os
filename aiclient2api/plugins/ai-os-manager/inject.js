(function() {
    const CSS_LINK = '<link rel="stylesheet" href="/plugins/ai-os-manager/styles.css">';
    const TOAST_CONTAINER = '<div class="aios-toast-container" id="aios-toast-container"></div>';

    function adminFetch(url, options = {}) {
        const token = localStorage.getItem('aios_admin_token') || '';
        const headers = { 'Content-Type': 'application/json', ...options.headers };
        if (token) headers['X-Admin-Token'] = token;
        return fetch(url, { ...options, headers }).then(r => {
            if (r.status === 401) {
                const newToken = prompt('请输入 Admin Token:');
                if (newToken) { localStorage.setItem('aios_admin_token', newToken); return adminFetch(url, options); }
                throw new Error('Unauthorized');
            }
            return r.json();
        });
    }

    function showToast(message, type = 'info') {
        const container = document.getElementById('aios-toast-container');
        if (!container) return;
        const toast = document.createElement('div');
        toast.className = `aios-toast aios-toast-${type}`;
        toast.innerHTML = `<span>${message}</span><button class="aios-toast-close" onclick="this.parentElement.remove()">×</button>`;
        container.appendChild(toast);
        setTimeout(() => toast.remove(), 4000);
    }

    function loadingHTML(text = '加载中...') {
        return `<div class="aios-loading">${text}</div>`;
    }

    function emptyHTML(text = '暂无数据') {
        return `<div class="aios-empty"><i class="fas fa-inbox"></i><span>${text}</span></div>`;
    }

    function errorHTML(msg) {
        return `<div class="aios-error">${msg}</div>`;
    }

    function formatBytes(bytes) {
        if (!bytes || bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
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
            <button class="aios-btn aios-btn-sm" onclick="AiosManager.gpu.refresh()"><i class="fas fa-sync-alt"></i> 刷新</button>
        </div>
    </div>
    <div class="aios-stats-grid" id="aios-gpu-stats"></div>
    <div class="aios-card aios-chart-card">
        <div class="aios-card-header"><h3><i class="fas fa-chart-area"></i> GPU 历史趋势</h3></div>
        <div class="aios-card-content">
            <canvas id="aios-gpu-chart" style="height:80px;"></canvas>
        </div>
    </div>
    <div class="aios-card aios-status-card" style="margin-top:var(--space-lg);">
        <div class="aios-card-header"><h3><i class="fas fa-bolt"></i> 引擎状态</h3></div>
        <div class="aios-card-content" id="aios-engine-status"></div>
    </div>
</div>`;

    const MODEL_HTML = `
<div class="section" id="section-aios-model" style="display:none;">
    <div class="section-header">
        <h2><i class="fas fa-cubes"></i> 模型管理</h2>
        <div class="section-actions">
            <button class="aios-btn aios-btn-sm" onclick="AiosManager.model.refresh()"><i class="fas fa-sync-alt"></i> 刷新</button>
        </div>
    </div>
    <div class="aios-status-banner" id="aios-model-banner">${loadingHTML()}</div>
    <div class="aios-card aios-action-card">
        <div class="aios-card-header"><h3><i class="fas fa-exchange-alt"></i> 快速切换</h3></div>
        <div class="aios-card-content">
            <div class="aios-form-grid">
                <div class="aios-form-group">
                    <label>模型</label>
                    <select id="aios-switch-model" class="aios-input aios-select"></select>
                </div>
                <div class="aios-form-group">
                    <label>引擎</label>
                    <select id="aios-switch-engine" class="aios-input aios-select">
                        <option value="vllm">vLLM</option>
                        <option value="sglang">SGLang</option>
                        <option value="llama_cpp">llama.cpp</option>
                    </select>
                </div>
                <div class="aios-form-group">
                    <label>端口</label>
                    <input id="aios-switch-port" class="aios-input" type="number" placeholder="自动">
                </div>
                <div class="aios-form-actions">
                    <button class="aios-btn aios-btn-primary" onclick="AiosManager.model.switchModel()"><i class="fas fa-play"></i> 切换</button>
                </div>
            </div>
            <div id="aios-switch-status" style="margin-top:var(--space-md);"></div>
        </div>
    </div>
    <div class="aios-models-shell" style="margin-top:var(--space-lg);">
        <div id="aios-model-list">${loadingHTML()}</div>
    </div>
    <div class="aios-card aios-action-card" style="margin-top:var(--space-lg);">
        <div class="aios-card-header"><h3><i class="fas fa-download"></i> 模型下载</h3></div>
        <div class="aios-card-content">
            <div class="aios-form-grid">
                <div class="aios-form-group" style="flex:2;">
                    <label>HuggingFace 模型ID</label>
                    <input id="aios-download-model-id" class="aios-input" placeholder="如: Qwen/Qwen2.5-7B-Instruct" style="width:100%;">
                </div>
                <div class="aios-form-actions">
                    <button class="aios-btn aios-btn-primary" onclick="AiosManager.model.download()"><i class="fas fa-cloud-download-alt"></i> 下载</button>
                </div>
            </div>
            <div id="aios-download-status" style="margin-top:var(--space-md);"></div>
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
        ];
        const menuHTML = dividerHTML + menuItems.join('');

        if (divider) {
            divider.insertAdjacentHTML('afterend', menuHTML);
        } else {
            navContainer.insertAdjacentHTML('beforeend', menuHTML);
        }

        contentContainer.insertAdjacentHTML('beforeend', GPU_HTML);
        contentContainer.insertAdjacentHTML('beforeend', MODEL_HTML);

        document.getElementById('nav-aios-gpu').addEventListener('click', (e) => {
            e.preventDefault();
            showSection('aios-gpu');
            AiosManager.gpu.refresh();
        });
        document.getElementById('nav-aios-model').addEventListener('click', (e) => {
            e.preventDefault();
            showSection('aios-model');
            AiosManager.model.refresh();
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
            history: { utilization: [], memory: [], temperature: [] },
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
                const result = data.data || data;
                const gpus = result.all_gpus || result.gpus || [result];
                if (!gpus || gpus.length === 0) {
                    document.getElementById('aios-gpu-stats').innerHTML = emptyHTML('未检测到 GPU');
                    return;
                }
                const gpu = gpus[0];
                const cards = [
                    { icon: 'fa-tag', label: '名称', value: gpu.name || gpu.gpu_name || '-', },
                    { icon: 'fa-chart-line', label: '利用率', value: `${gpu.utilization || gpu.gpu_util || 0}%`, progress: gpu.utilization || gpu.gpu_util || 0, ptype: gpu.utilization > 80 ? 'danger' : gpu.utilization > 50 ? 'warning' : 'success' },
                    { icon: 'fa-memory', label: '显存', value: `${formatBytes(gpu.memory_used || gpu.used_memory || 0)} / ${formatBytes(gpu.memory_total || gpu.total_memory || 0)}`, progress: gpu.memory_total ? ((gpu.memory_used || gpu.used_memory || 0) / gpu.memory_total * 100) : 0, ptype: (gpu.memory_used || gpu.used_memory || 0) / (gpu.memory_total || gpu.total_memory || 1) > 0.8 ? 'danger' : 'success' },
                    { icon: 'fa-thermometer-half', label: '温度', value: `${gpu.temperature || gpu.gpu_temp || 0}°C`, progress: gpu.temperature || gpu.gpu_temp || 0, ptype: (gpu.temperature || gpu.gpu_temp || 0) > 80 ? 'danger' : (gpu.temperature || gpu.gpu_temp || 0) > 60 ? 'warning' : 'success' },
                    { icon: 'fa-plug', label: '功耗', value: `${gpu.power || gpu.power_draw || 0}W`, },
                ];
                document.getElementById('aios-gpu-stats').innerHTML = cards.map(c => {
                    const prog = c.progress ? `<div class="aios-progress-bar"><div class="aios-progress-fill aios-${c.ptype}" style="width:${Math.min(c.progress, 100)}%"></div></div>` : '';
                    return `<div class="aios-stat-card"><div class="aios-stat-icon"><i class="fas ${c.icon}"></i></div><div class="aios-stat-body"><div class="aios-stat-label">${c.label}</div><div class="aios-stat-value">${c.value}</div>${prog}</div></div>`;
                }).join('');
            },
            renderEngineStatus(data) {
                const result = data.data || data;
                const services = result.services || result.engines || [];
                if (!services || services.length === 0) {
                    document.getElementById('aios-engine-status').innerHTML = emptyHTML('未检测到引擎');
                    return;
                }
                const engines = services.map(s => {
                    const name = s.engine_type || s.name || s.type || 'unknown';
                    const display = name === 'vllm' ? 'vLLM' : name === 'sglang' ? 'SGLang' : name === 'llama_cpp' ? 'llama.cpp' : name;
                    const running = s.running || s.is_running || s.status === 'running' || false;
                    const model = s.model_name || s.model || '-';
                    const port = s.port || '-';
                    const uptime = s.uptime_seconds ? `${Math.floor(s.uptime_seconds / 3600)}h${Math.floor((s.uptime_seconds % 3600) / 60)}m` : '-';
                    return { name, display, running, model, port, uptime };
                });
                const html = `<div class="aios-engine-grid">${engines.map(e => `
                    <div class="aios-engine-card ${e.running ? 'aios-engine-running' : 'aios-engine-stopped'}" data-engine="${e.name}" onclick="AiosManager.gpu.switchEngine('${e.name}')">
                        <div class="aios-engine-header">
                            <div class="aios-engine-icon"><i class="fas fa-bolt"></i></div>
                            <div class="aios-engine-title">${e.display}</div>
                        </div>
                        <div class="aios-engine-status-text ${e.running ? 'aios-engine-running-text' : 'aios-engine-stopped-text'}">
                            ${e.running ? '运行中' : '已停止'}
                        </div>
                        ${e.running ? `<div class="aios-engine-info"><div>模型: ${e.model}</div><div>端口: ${e.port}</div>${e.uptime !== '-' ? `<div>运行: ${e.uptime}</div>` : ''}</div>` : ''}
                        <div style="margin-top:auto;padding-top:var(--space-sm);">
                            <button class="aios-btn aios-btn-sm ${e.running ? 'aios-btn-success' : ''}" style="width:100%;">
                                <i class="fas ${e.running ? 'fa-check-circle' : 'fa-play'}"></i> ${e.running ? '当前引擎' : '切换到此引擎'}
                            </button>
                        </div>
                    </div>`).join('')}</div>`;
                document.getElementById('aios-engine-status').innerHTML = html;
            },
            async switchEngine(engineType) {
                try {
                    const aggResult = await adminFetch('/api/model-switch/aggregated');
                    const groups = aggResult.data?.groups || aggResult.groups || [];
                    let modelName = '';
                    for (const g of groups) {
                        for (const v of (g.variants || g.models || [])) {
                            if (v.status === 'running' || v.is_running) { modelName = v.model_name || v.name || g.group_name; break; }
                        }
                        if (modelName) break;
                    }
                    if (!modelName && groups.length > 0) modelName = groups[0].group_name || groups[0].name;
                    const result = await adminFetch('/api/engine/switch', {
                        method: 'POST',
                        body: JSON.stringify({ model_name: modelName, engine_type: engineType })
                    });
                    showToast(`切换引擎到 ${engineType} 成功`, 'success');
                    this.refresh();
                } catch (e) {
                    showToast(`切换引擎失败: ${e.message}`, 'error');
                }
            },
            updateHistory(data) {
                const result = data.data || data;
                const gpus = result.all_gpus || result.gpus || [result];
                const gpu = gpus[0];
                this.history.utilization.push(gpu.utilization || gpu.gpu_util || 0);
                this.history.memory.push(gpu.memory_used || gpu.used_memory || 0);
                this.history.temperature.push(gpu.temperature || gpu.gpu_temp || 0);
                const maxLen = 30;
                for (const k in this.history) {
                    if (this.history[k].length > maxLen) this.history[k] = this.history[k].slice(-maxLen);
                }
                drawMiniChart('aios-gpu-chart', this.history.utilization, maxLen);
            },
        },
        model: {
            async refresh() {
                try {
                    const [aggData, switchStatus, engineData] = await Promise.all([
                        adminFetch('/api/model-switch/aggregated'),
                        adminFetch('/api/model-switch/switch-status'),
                        adminFetch('/api/engine/status')
                    ]);
                    this.renderBanner(aggData, engineData);
                    this.renderModelList(aggData);
                    this.renderSwitchStatus(switchStatus);
                    this.populateModelSelect(aggData);
                    this.populateEngineSelect(engineData);
                } catch (e) {
                    document.getElementById('aios-model-banner').innerHTML = errorHTML(e.message);
                }
            },
            renderBanner(aggData, engineData) {
                const groups = aggData.data?.groups || aggData.groups || [];
                const engResult = engineData.data || engineData;
                const services = engResult.services || engResult.engines || [];
                let currentModel = '-', currentEngine = '-', currentPort = '-';
                for (const s of services) {
                    if (s.running || s.is_running) {
                        currentEngine = s.engine_type || s.name || '-';
                        currentModel = s.model_name || s.model || '-';
                        currentPort = s.port || '-';
                    }
                }
                if (currentModel === '-' && groups.length > 0) {
                    for (const g of groups) {
                        for (const v of (g.variants || g.models || [])) {
                            if (v.status === 'running' || v.is_running) { currentModel = v.model_name || v.name || g.group_name; break; }
                        }
                    }
                }
                const engineDisplay = currentEngine === 'vllm' ? 'vLLM' : currentEngine === 'sglang' ? 'SGLang' : currentEngine === 'llama_cpp' ? 'llama.cpp' : currentEngine;
                document.getElementById('aios-model-banner').innerHTML = `
                    <div class="aios-banner-title">当前运行状态</div>
                    <div class="aios-banner-cards">
                        <div class="aios-banner-item"><div class="aios-banner-icon"><i class="fas fa-bolt"></i></div><div class="aios-banner-info"><div class="aios-banner-label">引擎</div><div class="aios-banner-value aios-value-active">${engineDisplay}</div></div></div>
                        <div class="aios-banner-item"><div class="aios-banner-icon"><i class="fas fa-cube"></i></div><div class="aios-banner-info"><div class="aios-banner-label">模型</div><div class="aios-banner-value aios-value-active">${currentModel}</div></div></div>
                        <div class="aios-banner-item"><div class="aios-banner-icon"><i class="fas fa-hashtag"></i></div><div class="aios-banner-info"><div class="aios-banner-label">端口</div><div class="aios-banner-value">${currentPort}</div></div></div>
                    </div>`;
            },
            populateModelSelect(aggData) {
                const groups = aggData.data?.groups || aggData.groups || [];
                const select = document.getElementById('aios-switch-model');
                if (!select) return;
                select.innerHTML = groups.map(g => `<option value="${g.group_name || g.name}">${g.group_name || g.name}</option>`).join('');
            },
            populateEngineSelect(engineData) {
                const result = engineData.data || engineData;
                const services = result.services || result.engines || [];
                const select = document.getElementById('aios-switch-engine');
                if (!select) return;
                const engineTypes = ['vllm', 'sglang', 'llama_cpp'];
                select.innerHTML = engineTypes.map(t => {
                    const display = t === 'vllm' ? 'vLLM' : t === 'sglang' ? 'SGLang' : 'llama.cpp';
                    const running = services.find(s => (s.engine_type || s.name || s.type) === t && (s.running || s.is_running));
                    return `<option value="${t}" ${running ? 'selected' : ''}>${display}</option>`;
                }).join('');
            },
            renderModelList(aggData) {
                const groups = aggData.data?.groups || aggData.groups || [];
                if (!groups || groups.length === 0) {
                    document.getElementById('aios-model-list').innerHTML = emptyHTML('暂无模型');
                    return;
                }
                const html = `<div class="aios-models-list">${groups.map(g => {
                    const variants = g.variants || g.models || [];
                    const groupName = g.group_name || g.name;
                    const runningCount = variants.filter(v => v.status === 'running' || v.is_running).length;
                    return `<div class="aios-model-group">
                        <div class="aios-model-group-head">
                            <div class="aios-model-group-title">
                                <span class="aios-model-group-name">${groupName}</span>
                                <span class="aios-model-group-count">${variants.length} 个变体</span>
                            </div>
                            <div class="aios-model-group-stats">
                                <span class="aios-model-group-stat">${runningCount > 0 ? `<span style="color:var(--color-success)">${runningCount} 运行</span>` : '未运行'}</span>
                            </div>
                        </div>
                        <div class="aios-model-grid">${variants.map(v => {
                            const isRunning = v.status === 'running' || v.is_running;
                            const isCurrent = isRunning;
                            const vName = v.model_name || v.name || groupName;
                            const vEngine = v.engine_type || v.engine || '-';
                            const vPort = v.port || '-';
                            const vMemory = v.memory_usage || v.memory_used ? formatBytes(v.memory_usage || v.memory_used) : '-';
                            const engineDisplay = vEngine === 'vllm' ? 'vLLM' : vEngine === 'sglang' ? 'SGLang' : vEngine === 'llama_cpp' ? 'llama.cpp' : vEngine;
                            return `<div class="aios-model-item ${isCurrent ? 'aios-current-model' : ''}">
                                <div class="aios-model-header">
                                    <div class="aios-model-title-wrap">
                                        <div class="aios-model-name">${vName}</div>
                                        <div class="aios-model-tags">
                                            <span class="aios-model-status ${isRunning ? 'aios-running' : 'aios-stopped'}">${isRunning ? '运行中' : '已停止'}</span>
                                            ${isCurrent ? '<span class="aios-badge aios-badge-primary">当前</span>' : ''}
                                            <span class="aios-model-chip">${engineDisplay}</span>
                                        </div>
                                    </div>
                                </div>
                                <div class="aios-model-info-grid">
                                    <div class="aios-model-info-card"><div class="aios-model-info-label">端口</div><div class="aios-model-info-value">${vPort}</div></div>
                                    <div class="aios-model-info-card"><div class="aios-model-info-label">显存</div><div class="aios-model-info-value">${vMemory}</div></div>
                                    <div class="aios-model-info-card"><div class="aios-model-info-label">引擎</div><div class="aios-model-info-value">${engineDisplay}</div></div>
                                </div>
                                <div class="aios-model-actions">
                                    ${!isRunning ? `<button class="aios-btn aios-btn-sm aios-btn-success" onclick="AiosManager.model.start('${vName}')"><i class="fas fa-play"></i> 启动</button>` : ''}
                                    ${isRunning ? `<button class="aios-btn aios-btn-sm aios-btn-danger" onclick="AiosManager.model.stop('${vName}')"><i class="fas fa-stop"></i> 停止</button>` : ''}
                                    ${!isCurrent ? `<button class="aios-btn aios-btn-sm aios-btn-primary" onclick="AiosManager.model.switchTo('${vName}','${vEngine}')"><i class="fas fa-exchange-alt"></i> 切换</button>` : ''}
                                </div>
                            </div>`;
                        }).join('')}</div>
                    </div>`;
                }).join('')}</div>`;
                document.getElementById('aios-model-list').innerHTML = html;
            },
            renderSwitchStatus(data) {
                const result = data.data || data;
                const status = result.status || result.switch_status;
                const el = document.getElementById('aios-switch-status');
                if (!el) return;
                if (status === 'switching' || status === 'in_progress') {
                    el.innerHTML = `<div class="aios-switching">正在切换模型...</div>`;
                } else if (result.task_id) {
                    this.pollTask(result.task_id);
                } else {
                    el.innerHTML = '';
                }
            },
            async pollTask(taskId) {
                const el = document.getElementById('aios-switch-status');
                if (!el) return;
                el.innerHTML = `<div class="aios-switching">切换任务进行中...</div>`;
                try {
                    const result = await adminFetch(`/api/model-switch/task-status?taskId=${taskId}`);
                    const ts = result.data || result;
                    if (ts.status === 'completed' || ts.status === 'done') {
                        el.innerHTML = '';
                        showToast('模型切换完成', 'success');
                        this.refresh();
                    } else if (ts.status === 'failed' || ts.status === 'error') {
                        el.innerHTML = errorHTML(ts.error || '切换失败');
                        showToast('模型切换失败', 'error');
                    } else {
                        setTimeout(() => this.pollTask(taskId), 3000);
                    }
                } catch (e) {
                    el.innerHTML = errorHTML(e.message);
                }
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
                        method: 'POST',
                        body: JSON.stringify(body)
                    });
                    const data = result.data || result;
                    if (data.task_id) {
                        this.pollTask(data.task_id);
                    } else {
                        showToast(`切换到 ${modelName} 成功`, 'success');
                        this.refresh();
                    }
                } catch (e) {
                    showToast(`切换失败: ${e.message}`, 'error');
                }
            },
            async switchTo(modelName, engineType) {
                try {
                    const result = await adminFetch('/api/model-switch/switch', {
                        method: 'POST',
                        body: JSON.stringify({ modelName, engineType, async: true })
                    });
                    const data = result.data || result;
                    if (data.task_id) {
                        this.pollTask(data.task_id);
                    } else {
                        showToast(`切换到 ${modelName} 成功`, 'success');
                        this.refresh();
                    }
                } catch (e) {
                    showToast(`切换失败: ${e.message}`, 'error');
                }
            },
            async start(modelName) {
                try {
                    await adminFetch('/api/model-switch/start', { method: 'POST', body: JSON.stringify({ modelName }) });
                    showToast(`启动 ${modelName} 成功`, 'success');
                    this.refresh();
                } catch (e) { showToast(`启动失败: ${e.message}`, 'error'); }
            },
            async stop(modelName) {
                try {
                    await adminFetch('/api/model-switch/stop', { method: 'POST', body: JSON.stringify({ modelName }) });
                    showToast(`停止 ${modelName} 成功`, 'success');
                    this.refresh();
                } catch (e) { showToast(`停止失败: ${e.message}`, 'error'); }
            },
            async download() {
                const modelId = document.getElementById('aios-download-model-id').value.trim();
                if (!modelId) { showToast('请输入模型ID', 'warning'); return; }
                const statusEl = document.getElementById('aios-download-status');
                statusEl.innerHTML = `<div class="aios-loading">正在下载 ${modelId}...</div>`;
                try {
                    const result = await adminFetch('/api/model-switch/download', {
                        method: 'POST',
                        body: JSON.stringify({ modelId })
                    });
                    const data = result.data || result;
                    if (data.success || data.status === 'started') {
                        statusEl.innerHTML = `<div style="color:var(--color-success);padding:var(--space-md);">下载已开始: ${modelId}</div>`;
                        showToast(`开始下载 ${modelId}`, 'success');
                    } else {
                        statusEl.innerHTML = errorHTML(data.error || data.message || '下载失败');
                    }
                } catch (e) {
                    statusEl.innerHTML = errorHTML(e.message);
                    showToast(`下载失败: ${e.message}`, 'error');
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
            if (gpuVisible) AiosManager.gpu.refresh();
            if (modelVisible) AiosManager.model.refresh();
        }, 5000);
    }

    waitForDOM((nav, content) => {
        injectUI(nav, content);
        showSection('aios-gpu');
        startAutoRefresh();
    });
})();
