(function() {
    'use strict';

    const PLUGIN_ID = 'gpu-monitor-switch';
    const MENU_ID = 'nav-gpu-monitor';
    const SECTION_ID = 'section-gpu-monitor';
    const STYLE_ID = 'gpu-monitor-styles';

    const menuConfig = {
        id: MENU_ID,
        section: 'gpu-monitor',
        icon: 'fas fa-microchip',
        label: 'GPU 监控',
        insertAfter: 'nav-plugins',
    };

    const sectionHTML = `
<div id="gpu-monitor" class="section" data-section="gpu-monitor" style="display: none;">
    <div class="section-header">
        <h2><i class="fas fa-microchip"></i> <span>GPU 监控与模型管理</span></h2>
    </div>
    <div class="card">
        <div class="card-header">
            <h3><i class="fas fa-desktop"></i> <span>GPU 状态</span></h3>
            <button class="btn btn-sm btn-primary" id="gpuRefreshBtn"><i class="fas fa-sync-alt"></i> <span>刷新</span></button>
        </div>
        <div class="card-body"><div id="gpuStatusContent"><div class="loading-spinner"><i class="fas fa-spinner fa-spin"></i><span>加载中...</span></div></div></div>
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
        const link = document.createElement('link');
        link.id = STYLE_ID; link.rel = 'stylesheet'; link.href = '/plugins/gpu-monitor-switch/styles.css';
        document.head.appendChild(link);
        return true;
    }

    function renderGPUStatus(data) {
        if (!data || data.length === 0) {
            return '<div class="empty-state"><i class="fas fa-info-circle"></i><p>未检测到 GPU 设备</p></div>';
        }
        let html = '<div class="gpu-grid">';
        data.forEach(function(gpu) {
            var memUsed = gpu.memoryUsed ? (gpu.memoryUsed / 1024).toFixed(1) : '--';
            var memTotal = gpu.memoryTotal ? (gpu.memoryTotal / 1024).toFixed(1) : '--';
            var memPercent = gpu.memoryUsagePercent || 0;
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

    async function loadGPUData() {
        var el = document.getElementById('gpuStatusContent');
        if (!el) return;
        el.innerHTML = '<div class="loading-spinner"><i class="fas fa-spinner fa-spin"></i><span>加载中...</span></div>';
        try {
            var r = await fetch('/api/gpu-monitor');
            var result = await r.json();
            if (result.success && result.data && result.data.length > 0) {
                el.innerHTML = renderGPUStatus(result.data);
            } else {
                el.innerHTML = '<div class="empty-state"><i class="fas fa-info-circle"></i><p>未检测到 GPU 设备</p></div>';
            }
        } catch (e) {
            el.innerHTML = '<div class="empty-state error"><i class="fas fa-exclamation-triangle"></i><p>加载失败: ' + e.message + '</p></div>';
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
                    html += '<button class="btn btn-sm btn-primary" onclick="window.switchModel(\'' + model.name + '\')"><i class="fas fa-exchange-alt"></i> 切换</button>';
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
        try {
            var r = await fetch('/api/model-switch/switch', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ modelName: name }) });
            var result = await r.json();
            if (result.success) { alert('切换成功: ' + name); renderModels(); }
            else alert('切换失败: ' + result.error);
        } catch (e) { alert('切换失败: ' + e.message); }
    };

    window.startModel = async function(name) {
        try {
            var r = await fetch('/api/model-switch/start', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ modelName: name }) });
            var result = await r.json();
            if (result.success) { alert('启动成功: ' + name); renderModels(); }
            else alert('启动失败: ' + result.error);
        } catch (e) { alert('启动失败: ' + e.message); }
    };

    window.stopModel = async function(name) {
        try {
            var r = await fetch('/api/model-switch/stop', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ modelName: name }) });
            var result = await r.json();
            if (result.success) { alert('已停止: ' + name); renderModels(); }
            else alert('停止失败: ' + result.error);
        } catch (e) { alert('停止失败: ' + e.message); }
    };

    function injectMenuItem() {
        var nav = document.querySelector('.sidebar-nav');
        if (!nav) return false;
        if (document.getElementById(MENU_ID)) return true;
        var insertAfter = document.getElementById(menuConfig.insertAfter);
        var navItem = document.createElement('a');
        navItem.href = '#gpu-monitor'; navItem.className = 'nav-item'; navItem.id = menuConfig.id;
        navItem.dataset.section = menuConfig.section;
        navItem.innerHTML = '<i class="' + menuConfig.icon + '" aria-hidden="true"></i> <span>' + menuConfig.label + '</span>';
        if (insertAfter) insertAfter.after(navItem); else nav.appendChild(navItem);
        return true;
    }

    function injectSection() {
        var cc = document.getElementById('content-container');
        if (!cc) return false;
        if (document.getElementById(SECTION_ID)) return true;
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
        });
    }

    function bindEvents() {
        var btn = document.getElementById('gpuRefreshBtn');
        if (btn) btn.addEventListener('click', function() { loadGPUData(); renderModels(); });
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
