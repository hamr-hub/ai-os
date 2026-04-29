(function() {
    'use strict';

    var MENU_ID = 'nav-gpu-monitor';
    var STYLE_ID = 'gpu-monitor-styles';
    var REFRESH_INTERVAL = 5000;
    var MAX_HISTORY = 60;
    var gpuHistory = [];
    var autoRefreshTimer = null;
    var isAutoRefreshing = false;
    var gpuStatusRendered = false;
    var activeModelAction = null;
    var modelsRendered = false;

    var sectionHTML = `
<div id="gpu-monitor" class="section" data-section="gpu-monitor" style="display: none;">
    <div class="section-header">
        <h2><i class="fas fa-microchip"></i> <span>GPU 监控与模型管理</span></h2>
    </div>
    <div class="card">
        <div class="card-header">
            <h3><i class="fas fa-desktop"></i> <span>GPU 状态</span></h3>
            <div class="header-actions">
                <button class="btn btn-sm" id="gpuAutoRefreshBtn"><i class="fas fa-play"></i> <span>实时刷新</span></button>
                <button class="btn btn-sm btn-primary" id="gpuRefreshBtn"><i class="fas fa-sync-alt"></i> <span>刷新</span></button>
            </div>
        </div>
        <div class="card-body"><div id="gpuStatusContent"><div class="loading-spinner"><i class="fas fa-spinner fa-spin"></i><span>加载中...</span></div></div></div>
    </div>
    <div class="card" style="margin-top:20px;">
        <div class="card-header">
            <h3><i class="fas fa-chart-line"></i> <span>实时趋势</span></h3>
        </div>
        <div class="card-body">
            <div class="gpu-charts-grid">
                <div class="chart-card">
                    <div class="chart-title">GPU 使用率 (%)</div>
                    <canvas id="gpuUtilChart" width="320" height="140"></canvas>
                </div>
                <div class="chart-card">
                    <div class="chart-title">显存利用率 (%)</div>
                    <canvas id="gpuMemChart" width="320" height="140"></canvas>
                </div>
                <div class="chart-card">
                    <div class="chart-title">温度 (°C)</div>
                    <canvas id="gpuTempChart" width="320" height="140"></canvas>
                </div>
            </div>
        </div>
    </div>
    <div class="card" style="margin-top:20px;">
        <div class="card-header">
            <h3><i class="fas fa-cubes"></i> <span>模型管理</span></h3>
        </div>
        <div class="card-body"><div id="modelSwitchContent"><div class="loading-spinner"><i class="fas fa-spinner fa-spin"></i><span>加载中...</span></div></div></div>
    </div>
</div>`;

    function injectStyles() {
        if (document.getElementById(STYLE_ID)) return true;
        var link = document.createElement('link');
        link.id = STYLE_ID; link.rel = 'stylesheet'; link.href = '/plugins/gpu-monitor-switch/styles.css';
        document.head.appendChild(link);
        return true;
    }

    function drawLineChart(canvasId, data, maxVal, lineColor, fillColor) {
        var canvas = document.getElementById(canvasId);
        if (!canvas) return;
        var ctx = canvas.getContext('2d');
        var w = canvas.width;
        var h = canvas.height;
        var pad = { top: 10, bottom: 20, left: 35, right: 10 };
        var cw = w - pad.left - pad.right;
        var ch = h - pad.top - pad.bottom;

        ctx.clearRect(0, 0, w, h);

        ctx.fillStyle = '#1e293b';
        ctx.fillRect(0, 0, w, h);

        ctx.strokeStyle = '#334155';
        ctx.lineWidth = 0.5;
        ctx.font = '9px monospace';
        ctx.fillStyle = '#94a3b8';
        for (var i = 0; i <= 4; i++) {
            var yy = pad.top + (ch / 4) * i;
            ctx.beginPath();
            ctx.moveTo(pad.left, yy);
            ctx.lineTo(w - pad.right, yy);
            ctx.stroke();
            ctx.fillText(Math.round(maxVal - (maxVal / 4) * i), 2, yy + 3);
        }

        if (data.length < 2) return;

        var step = cw / (MAX_HISTORY - 1);
        var startIdx = MAX_HISTORY - data.length;

        ctx.beginPath();
        ctx.strokeStyle = lineColor;
        ctx.lineWidth = 2;
        for (var i = 0; i < data.length; i++) {
            var x = pad.left + (startIdx + i) * step;
            var y = pad.top + ch - (data[i] / maxVal) * ch;
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        }
        ctx.stroke();

        ctx.beginPath();
        for (var i = 0; i < data.length; i++) {
            var x = pad.left + (startIdx + i) * step;
            var y = pad.top + ch - (data[i] / maxVal) * ch;
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        }
        ctx.lineTo(pad.left + (startIdx + data.length - 1) * step, pad.top + ch);
        ctx.lineTo(pad.left + startIdx * step, pad.top + ch);
        ctx.closePath();
        ctx.fillStyle = fillColor;
        ctx.fill();

        var lastVal = data[data.length - 1];
        if (lastVal != null) {
            var lastX = pad.left + (startIdx + data.length - 1) * step;
            var lastY = pad.top + ch - (lastVal / maxVal) * ch;
            ctx.beginPath();
            ctx.arc(lastX, lastY, 3, 0, Math.PI * 2);
            ctx.fillStyle = lineColor;
            ctx.fill();
            ctx.font = 'bold 10px monospace';
            ctx.fillStyle = lineColor;
            ctx.fillText(lastVal.toFixed(1), lastX + 6, lastY - 2);
        }
    }

    function updateCharts() {
        var utilData = gpuHistory.map(function(h) { return h.utilization || 0; });
        var memData = gpuHistory.map(function(h) { return h.memory || 0; });
        var tempData = gpuHistory.map(function(h) { return h.temperature || 0; });
        drawLineChart('gpuUtilChart', utilData, 100, '#6366f1', 'rgba(99,102,241,0.15)');
        drawLineChart('gpuMemChart', memData, 100, '#06b6d4', 'rgba(6,182,212,0.15)');
        drawLineChart('gpuTempChart', tempData, 100, '#f59e0b', 'rgba(245,158,11,0.15)');
    }

    function renderGPUStatus(data) {
        if (!data || data.length === 0) {
            return '<div class="empty-state"><i class="fas fa-info-circle"></i><p>未检测到 GPU 设备</p></div>';
        }
        var html = '<div class="gpu-grid">';
        data.forEach(function(gpu) {
            var memUsed = gpu.memoryUsed ? (gpu.memoryUsed / (1024*1024*1024)).toFixed(1) : '--';
            var memTotal = gpu.memoryTotal ? (gpu.memoryTotal / (1024*1024*1024)).toFixed(1) : '--';
            var memPercent = gpu.memoryUsagePercent || gpu.memoryUtilization || 0;
            var gpuUtil = gpu.gpuUtilization || 0;
            var temp = gpu.temperature != null ? gpu.temperature : '--';
            var power = gpu.powerDraw != null ? gpu.powerDraw.toFixed(1) + 'W' : '--';
            var powerLimit = gpu.powerLimit != null ? gpu.powerLimit.toFixed(1) + 'W' : '';
            html += '<div class="gpu-card"><div class="gpu-header"><div class="gpu-name"><i class="fas fa-desktop"></i><span>#' + gpu.index + ' ' + gpu.name + '</span></div></div>';
            html += '<div class="gpu-metrics">';
            html += '<div class="metric"><div class="metric-label">GPU 使用率</div><div class="metric-value">' + gpuUtil.toFixed(1) + '%</div>';
            html += '<div class="progress-bar"><div class="progress-fill" style="width:' + gpuUtil + '%;background:' + getColor(gpuUtil) + '"></div></div></div>';
            html += '<div class="metric"><div class="metric-label">显存使用</div><div class="metric-value">' + memUsed + ' GB / ' + memTotal + ' GB</div>';
            html += '<div class="progress-bar"><div class="progress-fill" style="width:' + memPercent + '%;background:' + getColor(memPercent) + '"></div></div></div>';
            html += '<div class="metric"><div class="metric-label">温度</div><div class="metric-value">' + temp + (temp !== '--' ? '°C' : '') + '</div></div>';
            html += '<div class="metric"><div class="metric-label">功耗</div><div class="metric-value">' + power + (powerLimit ? ' / ' + powerLimit : '') + '</div></div>';
            html += '</div></div>';
        });
        html += '</div>';
        return html;
    }

    function getColor(v) { if (v < 60) return '#10b981'; if (v < 80) return '#f59e0b'; return '#ef4444'; }

    function updateGPUStatusInPlace(data) {
        if (!data || data.length === 0) return;
        var cards = document.querySelectorAll('#gpuStatusContent .gpu-card');
        data.forEach(function(gpu, i) {
            var card = cards[i];
            if (!card) return;
            var metrics = card.querySelectorAll('.metric');
            var memUsed = gpu.memoryUsed ? (gpu.memoryUsed / (1024*1024*1024)).toFixed(1) : '--';
            var memTotal = gpu.memoryTotal ? (gpu.memoryTotal / (1024*1024*1024)).toFixed(1) : '--';
            var memPercent = gpu.memoryUsagePercent || gpu.memoryUtilization || 0;
            var gpuUtil = gpu.gpuUtilization || 0;
            var temp = gpu.temperature != null ? gpu.temperature : '--';
            var power = gpu.powerDraw != null ? gpu.powerDraw.toFixed(1) + 'W' : '--';
            var powerLimit = gpu.powerLimit != null ? gpu.powerLimit.toFixed(1) + 'W' : '';

            if (metrics[0]) {
                metrics[0].querySelector('.metric-value').textContent = gpuUtil.toFixed(1) + '%';
                var fill0 = metrics[0].querySelector('.progress-fill');
                if (fill0) { fill0.style.width = gpuUtil + '%'; fill0.style.background = getColor(gpuUtil); }
            }
            if (metrics[1]) {
                metrics[1].querySelector('.metric-value').textContent = memUsed + ' GB / ' + memTotal + ' GB';
                var fill1 = metrics[1].querySelector('.progress-fill');
                if (fill1) { fill1.style.width = memPercent + '%'; fill1.style.background = getColor(memPercent); }
            }
            if (metrics[2]) {
                metrics[2].querySelector('.metric-value').textContent = temp + (temp !== '--' ? '°C' : '');
            }
            if (metrics[3]) {
                metrics[3].querySelector('.metric-value').textContent = power + (powerLimit ? ' / ' + powerLimit : '');
            }
        });
    }

    function setActionButtonsDisabled(disabled) {
        document.querySelectorAll('#modelSwitchContent .model-actions .btn').forEach(function(btn) {
            btn.disabled = disabled;
        });
    }

    function showModelMessage(type, text) {
        var el = document.getElementById('modelSwitchContent');
        var old = document.getElementById('gpu-model-message');
        if (old) old.remove();
        if (!el || !text) return;
        var div = document.createElement('div');
        div.id = 'gpu-model-message';
        div.className = type === 'error' ? 'empty-state error' : 'empty-state';
        div.style.marginBottom = '12px';
        div.innerHTML = '<p>' + text + '</p>';
        el.parentNode.insertBefore(div, el);
        if (type !== 'error') {
            setTimeout(function() {
                if (div && div.parentNode) div.parentNode.removeChild(div);
            }, 4000);
        }
    }

    function showSwitchingOverlay(modelName) {
        var old = document.getElementById('gpu-switching-overlay');
        if (old) old.remove();

        var overlay = document.createElement('div');
        overlay.id = 'gpu-switching-overlay';
        overlay.innerHTML = '<div class="switching-overlay">' +
            '<div class="switching-card">' +
            '<div class="switching-spinner"></div>' +
            '<div class="switching-title">正在切换模型</div>' +
            '<div class="switching-model">' + escapeHtml(modelName) + '</div>' +
            '<div class="switching-steps">' +
            '<div class="switching-step active" id="switch-step-1"><span class="step-dot"></span><span class="step-text">发送切换请求</span></div>' +
            '<div class="switching-step" id="switch-step-2"><span class="step-dot"></span><span class="step-text">后端加载模型</span></div>' +
            '<div class="switching-step" id="switch-step-3"><span class="step-dot"></span><span class="step-text">验证模型就绪</span></div>' +
            '</div>' +
            '<div class="switching-status" id="switch-elapsed">准备中...</div>' +
            '<div class="switching-hint">请勿关闭页面或重复操作</div>' +
            '</div></div>';
        document.body.appendChild(overlay);
    }

    function hideSwitchingOverlay() {
        var old = document.getElementById('gpu-switching-overlay');
        if (old) old.remove();
    }

    function escapeHtml(text) {
        var div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function updateSwitchingStatus(elapsed) {
        var status = document.getElementById('switch-elapsed');
        if (status) {
            var seconds = Math.floor(elapsed / 1000);
            status.textContent = '已等待 ' + seconds + ' 秒...';
        }
    }

    function updateSwitchingStep(step) {
        for (var i = 1; i <= 3; i++) {
            var el = document.getElementById('switch-step-' + i);
            if (!el) continue;
            el.classList.remove('active', 'done');
            if (i < step) el.classList.add('done');
            else if (i === step) el.classList.add('active');
        }
        var statusTexts = {
            1: '正在发送切换请求...',
            2: '后端正在加载模型，预计需要 1-2 分钟...',
            3: '正在验证模型是否就绪...'
        };
        var status = document.getElementById('switch-elapsed');
        if (status && statusTexts[step]) {
            status.textContent = statusTexts[step];
        }
    }

    async function executeModelAction(action, name, successText) {
        if (activeModelAction) return;
        activeModelAction = action + ':' + name;
        setActionButtonsDisabled(true);

        var actionLabel = action === 'switch' || action === 'start' ? '切换' : '停止';
        showModelMessage('info', '正在' + actionLabel + '模型：' + name + '...');

        if (action === 'switch' || action === 'start') {
            showSwitchingOverlay(name);
            updateSwitchingStep(1);
        }

        try {
            if (action === 'stop') {
                var r = await fetch('/api/model-switch/stop', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ modelName: name })
                });
                var result = await r.json();
                if (!result.success) {
                    hideSwitchingOverlay();
                    showModelMessage('error', '操作失败: ' + result.error);
                    activeModelAction = null;
                    setActionButtonsDisabled(false);
                    return;
                }
                hideSwitchingOverlay();
                activeModelAction = null;
                setActionButtonsDisabled(false);
                modelsRendered = false;
                await renderModels();
                showModelMessage('info', successText);
                return;
            }

            updateSwitchingStep(1);
            var r = await fetch('/api/model-switch/switch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ modelName: name })
            });
            var result = await r.json();

            if (!result.success) {
                hideSwitchingOverlay();
                showModelMessage('error', '切换失败: ' + (result.error || '未知错误'));
                activeModelAction = null;
                setActionButtonsDisabled(false);
                return;
            }

            hideSwitchingOverlay();
            activeModelAction = null;
            setActionButtonsDisabled(false);
            modelsRendered = false;
            await renderModels();
            loadGPUData();
            updateCharts();
            showModelMessage('info', successText);
        } catch (e) {
            hideSwitchingOverlay();
            showModelMessage('error', (action === 'switch' || action === 'start' ? '切换失败: ' : '操作失败: ') + e.message);
            activeModelAction = null;
            setActionButtonsDisabled(false);
        }
    }

    async function loadGPUData() {
        var el = document.getElementById('gpuStatusContent');
        if (!el) return;
        try {
            var r = await fetch('/api/gpu-monitor');
            var result = await r.json();
            if (result.success && result.data && result.data.length > 0) {
                if (!gpuStatusRendered) {
                    el.innerHTML = renderGPUStatus(result.data);
                    gpuStatusRendered = true;
                } else {
                    updateGPUStatusInPlace(result.data);
                }
                var gpu = result.data[0];
                gpuHistory.push({
                    utilization: gpu.gpuUtilization || 0,
                    memory: gpu.memoryUsagePercent || gpu.memoryUtilization || 0,
                    temperature: gpu.temperature != null ? gpu.temperature : 0,
                    timestamp: new Date().toISOString()
                });
                if (gpuHistory.length > MAX_HISTORY) gpuHistory.shift();
                updateCharts();
            } else if (!isAutoRefreshing) {
                el.innerHTML = '<div class="empty-state"><i class="fas fa-info-circle"></i><p>未检测到 GPU 设备</p></div>';
                gpuStatusRendered = false;
            }
        } catch (e) {
            if (!isAutoRefreshing) {
                el.innerHTML = '<div class="empty-state error"><i class="fas fa-exclamation-triangle"></i><p>加载失败: ' + e.message + '</p></div>';
            }
        }
    }

    function startAutoRefresh() {
        if (autoRefreshTimer) return;
        isAutoRefreshing = true;
        loadGPUData();
        autoRefreshTimer = setInterval(function() {
            loadGPUData();
        }, REFRESH_INTERVAL);
        var btn = document.getElementById('gpuAutoRefreshBtn');
        if (btn) {
            btn.innerHTML = '<i class="fas fa-pause"></i> <span>停止刷新</span>';
            btn.classList.add('btn-danger');
            btn.classList.remove('btn-default');
        }
    }

    function stopAutoRefresh() {
        isAutoRefreshing = false;
        if (autoRefreshTimer) { clearInterval(autoRefreshTimer); autoRefreshTimer = null; }
        var btn = document.getElementById('gpuAutoRefreshBtn');
        if (btn) {
            btn.innerHTML = '<i class="fas fa-play"></i> <span>实时刷新</span>';
            btn.classList.remove('btn-danger');
            btn.classList.add('btn-default');
        }
    }

    async function renderModels() {
        if (modelsRendered) return;
        var el = document.getElementById('modelSwitchContent');
        if (!el) return;

        function formatMemorySize(sizeMB) {
            if (!sizeMB || sizeMB <= 0) return 'N/A';
            if (sizeMB >= 1024) {
                return (sizeMB / 1024).toFixed(1) + ' GB';
            }
            return sizeMB.toFixed(0) + ' MB';
        }

        function getMemoryText(model) {
            return model.requiredMemory || (model.memoryGB ? model.memoryGB + 'GB' : 'N/A');
        }

        if (activeModelAction) {
            var actionParts = activeModelAction.split(':');
            var actionType = actionParts[0];
            var actionModel = actionParts.slice(1).join(':');
            el.innerHTML = '<div class="loading-spinner">' +
                '<i class="fas fa-spinner fa-spin"></i>' +
                '<span>正在' + (actionType === 'switch' ? '切换' : actionType === 'start' ? '启动' : '停止') + '模型：' + escapeHtml(actionModel) + '...</span>' +
                '</div>';
            return;
        }

        el.innerHTML = '<div class="loading-spinner"><i class="fas fa-spinner fa-spin"></i><span>加载中...</span></div>';
        try {
            var r = await fetch('/api/model-switch/models');
            var result = await r.json();
            if (!result.success || !result.data || result.data.length === 0) {
                el.innerHTML = '<div class="empty-state"><i class="fas fa-info-circle"></i><p>未找到模型</p></div>';
                return;
            }
            var runningModels = result.data.filter(function(m) { return m.running; });
            var stoppedModels = result.data.filter(function(m) { return !m.running; });
            var currentModel = runningModels.length > 0 ? runningModels[0] : null;
            var html = '<div class="model-list">';
            if (currentModel) {
                html += '<div class="model-item model-current">' +
                    '<div class="model-header">' +
                    '<div class="model-name">' +
                    '<i class="fas fa-check-circle" style="color:#22c55e;margin-right:6px;"></i>' +
                    escapeHtml(currentModel.name) +
                    '</div>' +
                    '<span class="model-status status-healthy">当前运行</span></div>';
                html += '<div class="model-details">' +
                    '<div class="detail-item"><span class="detail-label">类型</span><span class="detail-value">' + escapeHtml(currentModel.backendType || 'vllm') + '</span></div>' +
                    '<div class="detail-item"><span class="detail-label">大小</span><span class="detail-value">' + formatMemorySize(currentModel.sizeMB || currentModel.size_mb) + '</span></div>' +
                    '<div class="detail-item"><span class="detail-label">显存</span><span class="detail-value">' + getMemoryText(currentModel) + '</span></div>' +
                    '<div class="detail-item"><span class="detail-label">端口</span><span class="detail-value">' + (currentModel.port || '--') + '</span></div></div>';
                html += '<div class="model-actions">' +
                    '<button class="btn btn-sm btn-danger" onclick="window.stopModel(\'' + escapeHtml(currentModel.name) + '\')">' +
                    '<i class="fas fa-stop"></i> 停止</button></div></div>';
            }
            if (stoppedModels.length > 0) {
                html += '<div class="model-section-label" style="color:#94a3b8;font-size:0.9em;margin:16px 0 8px;padding-left:4px;">可切换的模型</div>';
                stoppedModels.forEach(function(model) {
                    html += '<div class="model-item model-switchable">' +
                        '<div class="model-header">' +
                        '<div class="model-name">' + escapeHtml(model.name) + '</div>' +
                        '<span class="model-status status-disabled">未运行</span></div>';
                    html += '<div class="model-details">' +
                        '<div class="detail-item"><span class="detail-label">类型</span><span class="detail-value">' + escapeHtml(model.backendType || 'vllm') + '</span></div>' +
                        '<div class="detail-item"><span class="detail-label">大小</span><span class="detail-value">' + formatMemorySize(model.sizeMB || model.size_mb) + '</span></div>' +
                        '<div class="detail-item"><span class="detail-label">显存</span><span class="detail-value">' + getMemoryText(model) + '</span></div>' +
                        '<div class="detail-item"><span class="detail-label">端口</span><span class="detail-value">' + (model.port || '--') + '</span></div></div>';
                    html += '<div class="model-actions">';
                    if (model.pathExists) {
                        html += '<button class="btn btn-sm btn-primary" onclick="window.switchModel(\'' + escapeHtml(model.name) + '\')">' +
                            '<i class="fas fa-exchange-alt"></i> 切换</button>' +
                            '<button class="btn btn-sm btn-success" onclick="window.startModel(\'' + escapeHtml(model.name) + '\')">' +
                            '<i class="fas fa-play"></i> 启动</button>';
                    } else {
                        html += '<span class="path-missing-tag" title="模型文件目录不存在: ' + escapeHtml(model.modelPath || model.name) + '">' +
                            '<i class="fas fa-exclamation-triangle"></i> 路径不存在</span>';
                    }
                    html += '</div></div>';
                });
            }
            html += '</div>';
            el.innerHTML = html;
            modelsRendered = true;
        } catch (e) {
            el.innerHTML = '<div class="empty-state error"><i class="fas fa-exclamation-triangle"></i><p>加载失败: ' + e.message + '</p></div>';
        }
    }

    window.switchModel = async function(name) {
        await executeModelAction('switch', name, '切换成功: ' + name);
    };

    window.startModel = async function(name) {
        await executeModelAction('start', name, '启动成功: ' + name);
    };

    window.stopModel = async function(name) {
        await executeModelAction('stop', name, '已停止: ' + name);
    };

    function injectMenuItem() {
        var nav = document.querySelector('.sidebar-nav');
        if (!nav) return false;
        if (document.getElementById(MENU_ID)) return true;
        var insertAfter = document.getElementById('nav-plugins');
        var navItem = document.createElement('a');
        navItem.href = '#gpu-monitor'; navItem.className = 'nav-item'; navItem.id = MENU_ID;
        navItem.dataset.section = 'gpu-monitor';
        navItem.innerHTML = '<i class="fas fa-microchip" aria-hidden="true"></i> <span>GPU 监控</span>';
        if (insertAfter) insertAfter.after(navItem); else nav.appendChild(navItem);
        return true;
    }

    function injectSection() {
        var cc = document.getElementById('content-container');
        if (!cc) return false;
        if (document.getElementById('gpu-monitor')) return true;
        cc.insertAdjacentHTML('beforeend', sectionHTML);
        return true;
    }

    function initNavigation() {
        var navItem = document.getElementById(MENU_ID);
        if (!navItem) return;
        navItem.addEventListener('click', function(e) {
            e.preventDefault();
            document.querySelectorAll('.nav-item').forEach(function(item) { item.classList.remove('active'); });
            navItem.classList.add('active');
            document.querySelectorAll('.section').forEach(function(s) { s.style.display = 'none'; });
            var target = document.getElementById('gpu-monitor');
            if (target) target.style.display = 'block';
            loadGPUData();
            renderModels();
            startAutoRefresh();
        });
    }

    function bindEvents() {
        var refreshBtn = document.getElementById('gpuRefreshBtn');
        if (refreshBtn) refreshBtn.addEventListener('click', function() { gpuStatusRendered = false; modelsRendered = false; loadGPUData(); renderModels(); });
        var autoBtn = document.getElementById('gpuAutoRefreshBtn');
        if (autoBtn) autoBtn.addEventListener('click', function() {
            if (isAutoRefreshing) stopAutoRefresh();
            else startAutoRefresh();
        });
    }

    function init() {
        injectStyles();
        if (injectMenuItem() && injectSection()) { initNavigation(); bindEvents(); }
    }

    function tryInit() {
        if (document.querySelector('.sidebar-nav') && document.getElementById('content-container')) init();
        else setTimeout(tryInit, 500);
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', tryInit);
    else tryInit();

})();
