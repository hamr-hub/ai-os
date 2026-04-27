(function() {
    'use strict';

    var MENU_ID = 'nav-gpu-monitor';
    var STYLE_ID = 'gpu-monitor-styles';
    var REFRESH_INTERVAL = 5000;
    var MAX_HISTORY = 60;
    var gpuHistory = [];
    var autoRefreshTimer = null;
    var isAutoRefreshing = false;
    var activeModelAction = null;

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

    async function executeModelAction(action, name, successText) {
        if (activeModelAction) return;
        activeModelAction = action + ':' + name;
        setActionButtonsDisabled(true);
        showModelMessage('info', action === 'switch' ? '正在切换并预热模型：' + name : '处理中：' + name);
        try {
            var r = await fetch('/api/model-switch/' + action, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ modelName: name })
            });
            var result = await r.json();
            if (!result.success) {
                showModelMessage('error', (action === 'switch' ? '切换失败: ' : '操作失败: ') + result.error);
                return;
            }
            await renderModels();
            if (action === 'switch') {
                var warmup = result.data && result.data.warmup;
                var providerUpdate = result.data && result.data.providerUpdate;
                if (warmup && warmup.success && providerUpdate && providerUpdate.success) {
                    showModelMessage('info', successText + '，预热完成，检测模型已同步');
                } else if (warmup && warmup.success) {
                    showModelMessage('info', successText + '，预热完成，但检测模型同步失败');
                } else if (warmup) {
                    showModelMessage('info', successText + '，但预热未成功');
                } else {
                    showModelMessage('info', successText);
                }
            } else {
                showModelMessage('info', successText);
            }
        } catch (e) {
            showModelMessage('error', (action === 'switch' ? '切换失败: ' : '操作失败: ') + e.message);
        } finally {
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
                el.innerHTML = renderGPUStatus(result.data);
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
        autoRefreshTimer = setInterval(function() { loadGPUData(); }, REFRESH_INTERVAL);
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
        var el = document.getElementById('modelSwitchContent');
        if (!el) return;
        el.innerHTML = '<div class="loading-spinner"><i class="fas fa-spinner fa-spin"></i><span>加载中...</span></div>';
        try {
            var r = await fetch('/api/model-switch/models');
            var result = await r.json();
            if (!result.success || !result.data || result.data.length === 0) {
                el.innerHTML = '<div class="empty-state"><i class="fas fa-info-circle"></i><p>未找到模型</p></div>';
                return;
            }
            var html = '<div class="model-list">';
            result.data.forEach(function(model) {
                var sc = model.running ? 'status-healthy' : 'status-disabled';
                var st = model.running ? '运行中' : '已停止';
                html += '<div class="model-item"><div class="model-header"><div class="model-name">' + model.name + '</div>';
                html += '<span class="model-status ' + sc + '">' + st + '</span></div>';
                html += '<div class="model-details"><div class="detail-item"><span class="detail-label">类型</span><span class="detail-value">' + (model.backendType || 'vllm') + '</span></div>';
                html += '<div class="detail-item"><span class="detail-label">端口</span><span class="detail-value">' + (model.port || '--') + '</span></div></div>';
                html += '<div class="model-actions">';
                if (model.running) {
                    html += '<button class="btn btn-sm btn-primary" onclick="window.switchModel(\'' + model.name + '\')"><i class="fas fa-exchange-alt"></i> 切换并预热</button>';
                    html += '<button class="btn btn-sm btn-danger" onclick="window.stopModel(\'' + model.name + '\')"><i class="fas fa-stop"></i> 停止</button>';
                } else {
                    html += '<button class="btn btn-sm btn-success" onclick="window.startModel(\'' + model.name + '\')"><i class="fas fa-play"></i> 启动</button>';
                }
                html += '</div></div>';
            });
            html += '</div>';
            el.innerHTML = html;
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
        if (refreshBtn) refreshBtn.addEventListener('click', function() { loadGPUData(); renderModels(); });
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
