(function() {
    'use strict';

    var panelFrame = document.getElementById('panel-frame');
    if (panelFrame) {
        function injectIntoIframe() {
            try {
                var iframeDoc = panelFrame.contentDocument || panelFrame.contentWindow.document;
                if (iframeDoc && iframeDoc.querySelector('.sidebar-nav')) {
                    var script = iframeDoc.createElement('script');
                    script.src = '/plugins/ai-os-manager/inject.js';
                    iframeDoc.body.appendChild(script);
                    console.log('[AI-OS Manager] Injected into iframe');
                    return true;
                }
            } catch(e) {
                console.log('[AI-OS Manager] Cannot access iframe yet:', e.message);
            }
            return false;
        }

        if (!injectIntoIframe()) {
            panelFrame.addEventListener('load', function() {
                var attempts = 0;
                var interval = setInterval(function() {
                    attempts++;
                    if (injectIntoIframe() || attempts > 30) {
                        clearInterval(interval);
                    }
                }, 500);
            });
        }
        return;
    }

    var MENU_IDS = {
        gpu: 'nav-aios-gpu',
        switch: 'nav-aios-switch',
        engine: 'nav-aios-engine',
        config: 'nav-aios-config',
        health: 'nav-aios-health',
        ratelimit: 'nav-aios-ratelimit',
    };
    var STYLE_ID = 'aios-manager-styles';
    var CONTAINER_ID = 'aios-container';

    var sectionHTML = '\
<div id="aios-gpu" class="section" data-section="aios-gpu" style="display: none;">\
    <div class="section-header">\
        <h2><i class="fas fa-microchip"></i> GPU监控</h2>\
        <div class="section-actions">\
            <button class="aios-btn aios-btn-sm" onclick="AiosManager.gpu.refresh()"><i class="fas fa-sync-alt"></i> 刷新</button>\
            <button class="aios-btn aios-btn-sm aios-btn-toggle" id="aios-gpu-auto-btn" onclick="AiosManager.gpu.toggleAutoRefresh()"><i class="fas fa-clock"></i> 自动刷新</button>\
        </div>\
    </div>\
    <div class="aios-dashboard">\
        <div class="aios-stats-grid">\
            <div class="aios-stat-card">\
                <div class="aios-stat-icon"><i class="fas fa-memory"></i></div>\
                <div class="aios-stat-body">\
                    <div class="aios-stat-label">GPU型号</div>\
                    <div class="aios-stat-value" id="aios-gpu-name">--</div>\
                </div>\
            </div>\
            <div class="aios-stat-card">\
                <div class="aios-stat-icon"><i class="fas fa-tachometer-alt"></i></div>\
                <div class="aios-stat-body">\
                    <div class="aios-stat-label">GPU利用率</div>\
                    <div class="aios-stat-value" id="aios-gpu-util">--</div>\
                    <div class="aios-progress-bar"><div class="aios-progress-fill" id="aios-gpu-util-bar"></div></div>\
                </div>\
            </div>\
            <div class="aios-stat-card">\
                <div class="aios-stat-icon"><i class="fas fa-database"></i></div>\
                <div class="aios-stat-body">\
                    <div class="aios-stat-label">显存使用</div>\
                    <div class="aios-stat-value" id="aios-gpu-mem">--</div>\
                    <div class="aios-progress-bar"><div class="aios-progress-fill" id="aios-gpu-mem-bar"></div></div>\
                </div>\
            </div>\
            <div class="aios-stat-card">\
                <div class="aios-stat-icon"><i class="fas fa-thermometer-half"></i></div>\
                <div class="aios-stat-body">\
                    <div class="aios-stat-label">温度</div>\
                    <div class="aios-stat-value" id="aios-gpu-temp">--</div>\
                </div>\
            </div>\
            <div class="aios-stat-card">\
                <div class="aios-stat-icon"><i class="fas fa-bolt"></i></div>\
                <div class="aios-stat-body">\
                    <div class="aios-stat-label">功耗</div>\
                    <div class="aios-stat-value" id="aios-gpu-power">--</div>\
                </div>\
            </div>\
        </div>\
        <div class="aios-chart-card">\
            <div class="aios-card-header">\
                <h3><i class="fas fa-chart-line"></i> 历史趋势</h3>\
            </div>\
            <div class="aios-card-content">\
                <canvas id="aios-gpu-history-chart" height="200"></canvas>\
            </div>\
        </div>\
        <div class="aios-table-card">\
            <div class="aios-card-header">\
                <h3><i class="fas fa-tasks"></i> GPU进程</h3>\
            </div>\
            <div class="aios-card-content">\
                <table class="aios-table" id="aios-gpu-processes">\
                    <thead><tr><th>PID</th><th>进程名</th><th>显存占用</th></tr></thead>\
                    <tbody><tr><td colspan="3" class="aios-empty">无进程</td></tr></tbody>\
                </table>\
            </div>\
        </div>\
    </div>\
</div>\
\
<div id="aios-switch" class="section" data-section="aios-switch" style="display: none;">\
    <div class="section-header">\
        <h2><i class="fas fa-exchange-alt"></i> 模型切换</h2>\
        <div class="section-actions">\
            <button class="aios-btn aios-btn-sm" onclick="AiosManager.modelSwitch.refresh()"><i class="fas fa-sync-alt"></i> 刷新</button>\
        </div>\
    </div>\
    <div class="aios-dashboard">\
        <div class="aios-status-banner">\
            <div class="aios-banner-title">当前运行状态</div>\
            <div class="aios-banner-cards">\
                <div class="aios-banner-item">\
                    <div class="aios-banner-icon"><i class="fas fa-bolt"></i></div>\
                    <div class="aios-banner-info">\
                        <div class="aios-banner-label">当前引擎</div>\
                        <div class="aios-banner-value" id="aios-current-engine">--</div>\
                    </div>\
                </div>\
                <div class="aios-banner-item">\
                    <div class="aios-banner-icon"><i class="fas fa-cube"></i></div>\
                    <div class="aios-banner-info">\
                        <div class="aios-banner-label">运行中模型</div>\
                        <div class="aios-banner-value" id="aios-current-model">--</div>\
                    </div>\
                </div>\
                <div class="aios-banner-item">\
                    <div class="aios-banner-icon"><i class="fas fa-plug"></i></div>\
                    <div class="aios-banner-info">\
                        <div class="aios-banner-label">服务端口</div>\
                        <div class="aios-banner-value" id="aios-current-port">--</div>\
                    </div>\
                </div>\
            </div>\
        </div>\
        <div class="aios-action-card">\
            <div class="aios-card-header">\
                <h3><i class="fas fa-random"></i> 快速切换</h3>\
            </div>\
            <div class="aios-card-content">\
                <div class="aios-form-grid">\
                    <div class="aios-form-group">\
                        <label>目标模型</label>\
                        <select id="aios-quick-switch-model" class="aios-input aios-select">\
                            <option value="">选择模型...</option>\
                        </select>\
                    </div>\
                    <div class="aios-form-group">\
                        <label>引擎</label>\
                        <select id="aios-quick-switch-engine" class="aios-input aios-select">\
                            <option value="vllm">vLLM</option>\
                            <option value="sglang">SGLang</option>\
                            <option value="llamacpp">llama.cpp</option>\
                        </select>\
                    </div>\
                    <div class="aios-form-group">\
                        <label>端口</label>\
                        <input type="number" id="aios-quick-switch-port" class="aios-input" value="8000" min="1024" max="65535">\
                    </div>\
                    <div class="aios-form-group aios-form-actions">\
                        <button class="aios-btn aios-btn-primary" onclick="AiosManager.modelSwitch.quickSwitch()"><i class="fas fa-exchange-alt"></i> 切换模型</button>\
                        <button class="aios-btn aios-btn-warning" onclick="AiosManager.modelSwitch.quickSwitchEngine()"><i class="fas fa-sync"></i> 切换引擎</button>\
                    </div>\
                </div>\
            </div>\
        </div>\
        <div class="aios-models-card" id="aios-models-container">\
            <div class="aios-loading">加载中...</div>\
        </div>\
        <div class="aios-status-card">\
            <div class="aios-card-header">\
                <h3><i class="fas fa-info-circle"></i> 切换状态</h3>\
            </div>\
            <div class="aios-card-content">\
                <div id="aios-switch-status-content">无进行中的切换</div>\
            </div>\
        </div>\
    </div>\
</div>\
\
<div id="aios-engine" class="section" data-section="aios-engine" style="display: none;">\
    <div class="section-header">\
        <h2><i class="fas fa-cogs"></i> 引擎管理</h2>\
        <div class="section-actions">\
            <button class="aios-btn aios-btn-sm" onclick="AiosManager.engine.refresh()"><i class="fas fa-sync-alt"></i> 刷新</button>\
        </div>\
    </div>\
    <div class="aios-dashboard">\
        <div class="aios-engine-grid">\
            <div class="aios-engine-card" data-engine="vllm">\
                <div class="aios-engine-header">\
                    <div class="aios-engine-icon"><i class="fas fa-bolt"></i></div>\
                    <div class="aios-engine-title">vLLM</div>\
                </div>\
                <div class="aios-engine-status" id="aios-engine-vllm-status">未运行</div>\
            </div>\
            <div class="aios-engine-card" data-engine="sglang">\
                <div class="aios-engine-header">\
                    <div class="aios-engine-icon"><i class="fas fa-rocket"></i></div>\
                    <div class="aios-engine-title">SGLang</div>\
                </div>\
                <div class="aios-engine-status" id="aios-engine-sglang-status">未运行</div>\
            </div>\
            <div class="aios-engine-card" data-engine="llamacpp">\
                <div class="aios-engine-header">\
                    <div class="aios-engine-icon"><i class="fas fa-leaf"></i></div>\
                    <div class="aios-engine-title">llama.cpp</div>\
                </div>\
                <div class="aios-engine-status" id="aios-engine-llamacpp-status">未运行</div>\
            </div>\
        </div>\
        <div class="aios-action-card">\
            <div class="aios-card-header">\
                <h3><i class="fas fa-random"></i> 引擎切换</h3>\
            </div>\
            <div class="aios-card-content">\
                <div class="aios-form-grid">\
                    <div class="aios-form-group">\
                        <label>模型</label>\
                        <select id="aios-engine-switch-model" class="aios-input aios-select">\
                            <option value="">选择模型...</option>\
                        </select>\
                    </div>\
                    <div class="aios-form-group">\
                        <label>目标引擎</label>\
                        <select id="aios-engine-switch-type" class="aios-input aios-select">\
                            <option value="vllm">vLLM</option>\
                            <option value="sglang">SGLang</option>\
                            <option value="llamacpp">llama.cpp</option>\
                        </select>\
                    </div>\
                    <div class="aios-form-group">\
                        <label>端口</label>\
                        <input type="number" id="aios-engine-switch-port" class="aios-input" value="8000" min="1024" max="65535">\
                    </div>\
                    <div class="aios-form-group aios-form-actions">\
                        <button class="aios-btn aios-btn-primary" onclick="AiosManager.engine.switchEngine()"><i class="fas fa-sync"></i> 切换引擎</button>\
                    </div>\
                </div>\
            </div>\
        </div>\
        <div class="aios-status-card">\
            <div class="aios-card-header">\
                <h3><i class="fas fa-list"></i> 引擎状态</h3>\
            </div>\
            <div class="aios-card-content">\
                <div id="aios-engine-status-content">加载中...</div>\
            </div>\
        </div>\
        <div class="aios-config-card">\
            <div class="aios-card-header">\
                <h3><i class="fas fa-sliders-h"></i> 引擎配置</h3>\
            </div>\
            <div class="aios-card-content">\
                <div id="aios-engine-config-content">加载中...</div>\
            </div>\
        </div>\
    </div>\
</div>\
\
<div id="aios-config" class="section" data-section="aios-config" style="display: none;">\
    <div class="section-header">\
        <h2><i class="fas fa-cog"></i> 配置中心</h2>\
        <div class="section-actions">\
            <button class="aios-btn aios-btn-sm" onclick="AiosManager.config.refresh()"><i class="fas fa-sync-alt"></i> 刷新</button>\
            <button class="aios-btn aios-btn-sm aios-btn-primary" onclick="AiosManager.config.save()"><i class="fas fa-save"></i> 保存</button>\
        </div>\
    </div>\
    <div class="aios-dashboard">\
        <div class="aios-config-card">\
            <div class="aios-card-header">\
                <h3><i class="fas fa-globe"></i> 全局配置</h3>\
            </div>\
            <div class="aios-card-content">\
                <form id="aios-global-config-form" class="aios-config-form"></form>\
            </div>\
        </div>\
        <div class="aios-config-card">\
            <div class="aios-card-header">\
                <h3><i class="fas fa-microchip"></i> vLLM默认配置</h3>\
            </div>\
            <div class="aios-card-content">\
                <form id="aios-vllm-config-form" class="aios-config-form"></form>\
            </div>\
        </div>\
        <div class="aios-config-card">\
            <div class="aios-card-header">\
                <h3><i class="fas fa-star"></i> 默认模型</h3>\
            </div>\
            <div class="aios-card-content">\
                <div class="aios-form-row">\
                    <input type="text" id="aios-default-model-input" placeholder="输入模型名称" class="aios-input">\
                    <button class="aios-btn aios-btn-primary" onclick="AiosManager.config.setDefaultModel()"><i class="fas fa-check"></i> 设置</button>\
                    <button class="aios-btn aios-btn-danger" onclick="AiosManager.config.clearDefaultModel()"><i class="fas fa-trash"></i> 清除</button>\
                </div>\
                <div id="aios-current-default-model" class="aios-config-info">当前默认模型: --</div>\
            </div>\
        </div>\
    </div>\
</div>\
\
<div id="aios-health" class="section" data-section="aios-health" style="display: none;">\
    <div class="section-header">\
        <h2><i class="fas fa-heartbeat"></i> 健康运维</h2>\
        <div class="section-actions">\
            <button class="aios-btn aios-btn-sm" onclick="AiosManager.health.refresh()"><i class="fas fa-sync-alt"></i> 刷新</button>\
            <button class="aios-btn aios-btn-sm aios-btn-primary" onclick="AiosManager.health.runCheck()"><i class="fas fa-stethoscope"></i> 运行检查</button>\
        </div>\
    </div>\
    <div class="aios-dashboard">\
        <div class="aios-health-banner">\
            <div class="aios-health-score">\
                <div class="aios-score-ring" id="aios-health-score-circle">\
                    <span id="aios-health-score-value">--</span>\
                </div>\
                <div class="aios-score-label">健康评分</div>\
            </div>\
            <div class="aios-health-status">\
                <h3>系统状态</h3>\
                <div id="aios-health-status-content">加载中...</div>\
            </div>\
        </div>\
        <div class="aios-alerts-card">\
            <div class="aios-card-header">\
                <h3><i class="fas fa-bell"></i> 告警信息</h3>\
            </div>\
            <div class="aios-card-content">\
                <div id="aios-alerts-container">无告警</div>\
            </div>\
        </div>\
        <div class="aios-system-card">\
            <div class="aios-card-header">\
                <h3><i class="fas fa-desktop"></i> 系统资源</h3>\
            </div>\
            <div class="aios-card-content">\
                <div class="aios-stats-grid">\
                    <div class="aios-metric-card">\
                        <div class="aios-metric-icon"><i class="fas fa-microchip"></i></div>\
                        <div class="aios-metric-body">\
                            <div class="aios-metric-label">CPU使用率</div>\
                            <div class="aios-metric-value" id="aios-cpu-util">--</div>\
                            <div class="aios-progress-bar"><div class="aios-progress-fill" id="aios-cpu-bar"></div></div>\
                        </div>\
                    </div>\
                    <div class="aios-metric-card">\
                        <div class="aios-metric-icon"><i class="fas fa-memory"></i></div>\
                        <div class="aios-metric-body">\
                            <div class="aios-metric-label">内存使用</div>\
                            <div class="aios-metric-value" id="aios-mem-util">--</div>\
                            <div class="aios-progress-bar"><div class="aios-progress-fill" id="aios-mem-bar"></div></div>\
                        </div>\
                    </div>\
                    <div class="aios-metric-card">\
                        <div class="aios-metric-icon"><i class="fas fa-hdd"></i></div>\
                        <div class="aios-metric-body">\
                            <div class="aios-metric-label">磁盘使用</div>\
                            <div class="aios-metric-value" id="aios-disk-util">--</div>\
                            <div class="aios-progress-bar"><div class="aios-progress-fill" id="aios-disk-bar"></div></div>\
                        </div>\
                    </div>\
                </div>\
            </div>\
        </div>\
        <div class="aios-chart-card">\
            <div class="aios-card-header">\
                <h3><i class="fas fa-chart-line"></i> 健康历史</h3>\
            </div>\
            <div class="aios-card-content">\
                <canvas id="aios-health-history-chart" height="150"></canvas>\
            </div>\
        </div>\
    </div>\
</div>\
\
<div id="aios-ratelimit" class="section" data-section="aios-ratelimit" style="display: none;">\
    <div class="section-header">\
        <h2><i class="fas fa-tachometer-alt"></i> 限流控制</h2>\
        <div class="section-actions">\
            <button class="aios-btn aios-btn-sm" onclick="AiosManager.ratelimit.refresh()"><i class="fas fa-sync-alt"></i> 刷新</button>\
            <button class="aios-btn aios-btn-sm aios-btn-primary" onclick="AiosManager.ratelimit.saveConfig()"><i class="fas fa-save"></i> 保存配置</button>\
        </div>\
    </div>\
    <div class="aios-dashboard">\
        <div class="aios-status-card">\
            <div class="aios-card-header">\
                <h3><i class="fas fa-list-ul"></i> 队列状态</h3>\
            </div>\
            <div class="aios-card-content">\
                <div id="aios-queue-content">加载中...</div>\
            </div>\
        </div>\
        <div class="aios-config-card">\
            <div class="aios-card-header">\
                <h3><i class="fas fa-sliders-h"></i> 限流配置</h3>\
            </div>\
            <div class="aios-card-content">\
                <form id="aios-ratelimit-config-form" class="aios-config-form"></form>\
            </div>\
        </div>\
        <div class="aios-stats-card">\
            <div class="aios-card-header">\
                <h3><i class="fas fa-chart-bar"></i> 限流统计</h3>\
            </div>\
            <div class="aios-card-content">\
                <div id="aios-ratelimit-stats-content">加载中...</div>\
            </div>\
        </div>\
    </div>\
</div>';

    var _logger = function(message) {
        console.log('[AI-OS Manager]', message);
    };

    function escapeHtml(str) {
        return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function formatBytes(bytes) {
        if (!bytes || bytes === 0) return '0 B';
        var k = 1024;
        var sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        var i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    function formatPercent(value) {
        if (value === null || value === undefined) return '--';
        return (typeof value === 'number' ? value.toFixed(1) : value) + '%';
    }

    function getAdminToken() {
        try { return localStorage.getItem('aios_admin_token') || ''; } catch(e) { return ''; }
    }

    function adminFetch(url, options) {
        options = options || {};
        var token = getAdminToken();
        if (token) {
            options.headers = options.headers || {};
            options.headers['X-Admin-Token'] = token;
        }
        return fetch(url, options);
    }

    function promptForToken() {
        var existing = getAdminToken();
        var token = window.prompt('请输入管理员令牌 (Admin Token):', existing);
        if (token) {
            try { localStorage.setItem('aios_admin_token', token); } catch(e) {}
        }
    }

    function createMiniBar(percent, colorClass) {
        var p = Math.min(100, Math.max(0, percent || 0));
        return '<div class="aios-progress-bar"><div class="aios-progress-fill ' + (colorClass || '') + '" style="width:' + p + '%"></div></div>';
    }

    function drawLineChart(canvasId, datasets, labels) {
        var canvas = document.getElementById(canvasId);
        if (!canvas) return;
        var ctx = canvas.getContext('2d');
        var width = canvas.width;
        var height = canvas.height;
        ctx.clearRect(0, 0, width, height);

        var padding = 40;
        var chartW = width - padding * 2;
        var chartH = height - padding * 2;

        var allValues = [];
        datasets.forEach(function(ds) { allValues = allValues.concat(ds.data); });
        var maxVal = Math.max.apply(null, allValues) || 100;
        var minVal = Math.min.apply(null, allValues) || 0;

        ctx.strokeStyle = '#e0e0e0';
        ctx.lineWidth = 1;
        for (var i = 0; i <= 4; i++) {
            var y = padding + (chartH / 4) * i;
            ctx.beginPath();
            ctx.moveTo(padding, y);
            ctx.lineTo(width - padding, y);
            ctx.stroke();
            ctx.fillStyle = '#8b949e';
            ctx.font = '10px sans-serif';
            ctx.textAlign = 'right';
            ctx.fillText(Math.round(maxVal - (maxVal - minVal) / 4 * i), padding - 5, y + 3);
        }

        var colors = ['#22c55e', '#3b82f6', '#f59e0b', '#ef4444'];
        datasets.forEach(function(ds, di) {
            var color = colors[di % colors.length];
            ctx.strokeStyle = color;
            ctx.lineWidth = 2;
            ctx.beginPath();
            ds.data.forEach(function(val, j) {
                var x = padding + (chartW / Math.max(1, ds.data.length - 1)) * j;
                var y = padding + chartH - ((val - minVal) / (maxVal - minVal || 1)) * chartH;
                if (j === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            });
            ctx.stroke();

            ctx.fillStyle = color;
            ctx.font = '11px sans-serif';
            ctx.textAlign = 'left';
            ctx.fillText(ds.label || ('系列' + (di + 1)), padding, padding - 10 - di * 15);
        });
    }

    function injectStyles() {
        if (document.getElementById(STYLE_ID)) return true;
        var link = document.createElement('link');
        link.id = STYLE_ID; link.rel = 'stylesheet';
        link.href = '/plugins/ai-os-manager/styles.css';
        document.head.appendChild(link);
        _logger('Styles injected');
        return true;
    }

    function injectMenuItems() {
        var nav = document.querySelector('.sidebar-nav');
        if (!nav) {
            _logger('Sidebar not found');
            return false;
        }

        var items = [
            { id: MENU_IDS.gpu, section: 'aios-gpu', icon: 'fa-microchip', label: 'GPU监控' },
            { id: MENU_IDS.switch, section: 'aios-switch', icon: 'fa-exchange-alt', label: '模型切换' },
            { id: MENU_IDS.engine, section: 'aios-engine', icon: 'fa-bolt', label: '引擎管理' },
            { id: MENU_IDS.config, section: 'aios-config', icon: 'fa-cog', label: '配置中心' },
            { id: MENU_IDS.health, section: 'aios-health', icon: 'fa-heartbeat', label: '健康运维' },
            { id: MENU_IDS.ratelimit, section: 'aios-ratelimit', icon: 'fa-tachometer-alt', label: '限流控制' },
        ];

        var pluginDivider = document.getElementById('nav-plugins-divider');
        if (!pluginDivider) {
            pluginDivider = document.createElement('div');
            pluginDivider.id = 'nav-plugins-divider';
            pluginDivider.className = 'nav-divider';
            pluginDivider.style.cssText = 'margin: 8px 16px; border-bottom: 1px solid rgba(255,255,255,0.1);';
            var anchor = document.getElementById('nav-plugins');
            if (!anchor) {
                var pluginItems = nav.querySelectorAll('.nav-item');
                for (var i = 0; i < pluginItems.length; i++) {
                    if (pluginItems[i].dataset.section === 'plugins') {
                        anchor = pluginItems[i];
                        break;
                    }
                }
            }
            if (anchor) anchor.before(pluginDivider);
            else nav.appendChild(pluginDivider);
            _logger('Divider created');
        }

        items.forEach(function(item) {
            if (document.getElementById(item.id)) return;
            var navItem = document.createElement('a');
            navItem.href = '#' + item.section;
            navItem.className = 'nav-item';
            navItem.id = item.id;
            navItem.dataset.section = item.section;
            navItem.innerHTML = '<i class="fas ' + item.icon + '" aria-hidden="true"></i> <span>' + item.label + '</span>';
            pluginDivider.after(navItem);
        });
        _logger('Menu items injected');
        return true;
    }

    function injectSections() {
        var cc = document.getElementById('content-container');
        if (!cc) {
            _logger('Content container not found');
            return false;
        }
        if (document.getElementById('aios-gpu')) {
            _logger('Sections already present');
            return true;
        }
        cc.insertAdjacentHTML('beforeend', sectionHTML);
        _logger('Sections injected');
        return true;
    }

    function initNavigation() {
        Object.keys(MENU_IDS).forEach(function(key) {
            var navItem = document.getElementById(MENU_IDS[key]);
            if (!navItem) return;
            navItem.addEventListener('click', function(e) {
                e.preventDefault();
                document.querySelectorAll('.nav-item').forEach(function(i) { i.classList.remove('active'); });
                navItem.classList.add('active');
                document.querySelectorAll('.section').forEach(function(s) { s.style.display = 'none'; });
                var sectionId = navItem.dataset.section;
                var section = document.getElementById(sectionId);
                if (section) section.style.display = 'block';
                _activeSection = sectionId;
                loadData(sectionId);
            });
        });
        _logger('Navigation initialized');
    }

    var _activeSection = null;
    var _refreshTimer = null;
    var _observer = null;
    var REFRESH_INTERVAL = 5000;

    function startAutoRefresh() {
        stopAutoRefresh();
        _refreshTimer = setInterval(function() {
            if (_activeSection) loadData(_activeSection);
        }, REFRESH_INTERVAL);
    }

    function stopAutoRefresh() {
        if (_refreshTimer) { clearInterval(_refreshTimer); _refreshTimer = null; }
    }

    function checkDOMAndInit() {
        var sidebarExists = !!document.querySelector('.sidebar-nav');
        var contentExists = !!document.getElementById('content-container');
        if (sidebarExists && contentExists) {
            _logger('Required elements found, initializing');
            init();
            return true;
        }
        _logger('DOM not ready: sidebar=' + sidebarExists + ', content=' + contentExists);
        return false;
    }

    function setupObserver() {
        if (!('MutationObserver' in window)) {
            _logger('MutationObserver not supported');
            return;
        }
        _observer = new MutationObserver(function(mutations) {
            var injected = document.getElementById('aios-gpu');
            if (!injected) {
                checkDOMAndInit();
            }
        });
        _observer.observe(document.body, {
            childList: true,
            subtree: true
        });
        _logger('MutationObserver set up');
    }

    var _pollInterval = null;
    function startPolling() {
        var attempts = 0;
        _pollInterval = setInterval(function() {
            attempts++;
            if (checkDOMAndInit()) {
                clearInterval(_pollInterval);
                _pollInterval = null;
                return;
            }
            if (attempts > 60) {
                clearInterval(_pollInterval);
                _pollInterval = null;
                _logger('Polling stopped after ' + attempts + ' attempts');
            }
        }, 500);
    }

    function init() {
        injectStyles();
        if (injectMenuItems() && injectSections()) {
            initNavigation();
            startAutoRefresh();
            AiosManager.gpu.initChart();
            AiosManager.health.initChart();
            _logger('Plugin fully initialized');
        }
    }

    window.AiosManager = {
        gpu: {
            _autoRefresh: false,
            _gpuHistory: [],

            initChart: function() {
                var canvas = document.getElementById('aios-gpu-history-chart');
                if (canvas) {
                    canvas.width = canvas.parentElement.offsetWidth - 40;
                    canvas.height = 200;
                }
            },

            refresh: function() {
                adminFetch('/api/gpu-monitor/info').then(function(r) {
                    if (r.status === 401) { promptForToken(); return null; }
                    return r.json();
                }).then(function(data) {
                    if (!data || !data.data) {
                        document.getElementById('aios-gpu-name').textContent = '无GPU数据';
                        return;
                    }
                    var innerData = data.data;
                    var gpuList = null;
                    if (Array.isArray(innerData)) gpuList = innerData;
                    else if (innerData && Array.isArray(innerData.data)) gpuList = innerData.data;
                    else if (innerData && innerData.data && innerData.data.data) gpuList = innerData.data.data;

                    if (!gpuList || !gpuList.length) {
                        document.getElementById('aios-gpu-name').textContent = '无GPU数据';
                        return;
                    }
                    var gpu = gpuList[0];
                    document.getElementById('aios-gpu-name').textContent = gpu.name || '--';
                    document.getElementById('aios-gpu-util').textContent = formatPercent(gpu.gpuUtilization);
                    document.getElementById('aios-gpu-util-bar').style.width = (gpu.gpuUtilization || 0) + '%';
                    document.getElementById('aios-gpu-util-bar').className = 'aios-progress-fill ' + ((gpu.gpuUtilization || 0) > 80 ? 'aios-danger' : (gpu.gpuUtilization || 0) > 50 ? 'aios-warning' : 'aios-success');

                    var memUsed = gpu.memoryUsed || 0;
                    var memTotal = gpu.memoryTotal || 1;
                    var memPercent = (memUsed / memTotal * 100);
                    document.getElementById('aios-gpu-mem').textContent = formatBytes(memUsed) + ' / ' + formatBytes(memTotal);
                    document.getElementById('aios-gpu-mem-bar').style.width = memPercent + '%';
                    document.getElementById('aios-gpu-mem-bar').className = 'aios-progress-fill ' + (memPercent > 90 ? 'aios-danger' : memPercent > 70 ? 'aios-warning' : 'aios-success');

                    document.getElementById('aios-gpu-temp').textContent = gpu.temperature ? gpu.temperature + '°C' : '--';
                    document.getElementById('aios-gpu-power').textContent = (gpu.powerDraw != null) ? gpu.powerDraw + 'W / ' + (gpu.powerLimit || '--') + 'W' : '--';

                    if (data.history && data.history.length > 1) {
                        AiosManager.gpu._gpuHistory = data.history;
                        var utilData = data.history.map(function(h) { return h.utilization || 0; });
                        var memData = data.history.map(function(h) { return h.memory || 0; });
                        var labels = data.history.map(function(h) { return new Date(h.timestamp).toLocaleTimeString(); });
                        drawLineChart('aios-gpu-history-chart', [
                            { label: 'GPU利用率', data: utilData },
                            { label: '显存使用率', data: memData }
                        ], labels);
                    }

                    if (gpu.processes && gpu.processes.length > 0) {
                        var tbody = document.querySelector('#aios-gpu-processes tbody');
                        tbody.innerHTML = gpu.processes.map(function(p) {
                            return '<tr><td>' + p.pid + '</td><td>' + escapeHtml(p.name || '--') + '</td><td>' + formatBytes(p.gpu_memory_usage || p.used_memory || 0) + '</td></tr>';
                        }).join('');
                    }
                }).catch(function(err) {
                    document.getElementById('aios-gpu-name').textContent = '错误: ' + err.message;
                });
            },

            toggleAutoRefresh: function() {
                AiosManager.gpu._autoRefresh = !AiosManager.gpu._autoRefresh;
                var btn = document.getElementById('aios-gpu-auto-btn');
                if (AiosManager.gpu._autoRefresh) {
                    btn.textContent = '停止刷新';
                    btn.classList.add('aios-btn-active');
                    startAutoRefresh();
                } else {
                    btn.textContent = '自动刷新';
                    btn.classList.remove('aios-btn-active');
                    stopAutoRefresh();
                }
            }
        },

        modelSwitch: {
            _currentEngine: null,
            _currentModel: null,
            _currentPort: null,
            _allModels: [],

            refresh: function() {
                adminFetch('/api/engine/status').then(function(r) {
                    if (r.status === 401) { promptForToken(); return null; }
                    return r.json();
                }).then(function(engineData) {
                    var engineEl = document.getElementById('aios-current-engine');
                    var portEl = document.getElementById('aios-current-port');
                    if (engineData && engineData.data) {
                        var d = engineData.data;
                        var currentEngine = d.engine_manager_mode || '--';
                        if (d.services && d.services.length > 0) {
                            var activeService = d.services.find(function(s) { return s.status === 'running'; });
                            if (activeService) {
                                currentEngine = activeService.engine_type || currentEngine;
                                AiosManager.modelSwitch._currentPort = activeService.port;
                                portEl.textContent = activeService.port || '--';
                            } else {
                                portEl.textContent = '--';
                            }
                        } else {
                            portEl.textContent = '--';
                        }
                        AiosManager.modelSwitch._currentEngine = currentEngine;
                        engineEl.textContent = currentEngine;
                        var engineSelect = document.getElementById('aios-quick-switch-engine');
                        if (engineSelect) engineSelect.value = currentEngine;
                    } else {
                        engineEl.textContent = '未运行';
                        portEl.textContent = '--';
                    }
                }).catch(function() {
                    document.getElementById('aios-current-engine').textContent = '获取失败';
                    document.getElementById('aios-current-port').textContent = '--';
                });

                adminFetch('/api/model-switch/aggregated').then(function(r) {
                    if (r.status === 401) { promptForToken(); return null; }
                    return r.json();
                }).then(function(data) {
                    if (!data || !data.data || !data.data.groups) {
                        document.getElementById('aios-models-container').innerHTML = '<div class="aios-empty">无模型数据</div>';
                        return;
                    }
                    var currentModel = data.data.current_model || null;
                    AiosManager.modelSwitch._currentModel = currentModel;
                    var modelEl = document.getElementById('aios-current-model');
                    modelEl.textContent = currentModel || '无运行模型';
                    if (currentModel) {
                        modelEl.classList.add('aios-value-active');
                    } else {
                        modelEl.classList.remove('aios-value-active');
                    }

                    var allModels = [];
                    var html = '';
                    data.data.groups.forEach(function(group) {
                        html += '<div class="aios-model-group"><h5>' + escapeHtml(group.base_name) + '</h5>';
                        group.variants.forEach(function(v) {
                            allModels.push(v);
                            var statusClass = v.running ? 'aios-running' : 'aios-stopped';
                            var isCurrent = v.is_current ? ' aios-current-model' : '';
                            html += '<div class="aios-model-item' + isCurrent + '">';
                            html += '<div class="aios-model-header">';
                            html += '<span class="aios-model-name">' + escapeHtml(v.name) + '</span>';
                            html += '<span class="aios-model-status ' + statusClass + '">' + (v.running ? '运行中' : '已停止') + '</span>';
                            if (v.is_current) html += '<span class="aios-badge aios-badge-primary">当前</span>';
                            html += '</div>';
                            html += '<div class="aios-model-info">';
                            html += '<span>后端: ' + escapeHtml(v.backend_type || 'vllm') + '</span>';
                            html += '<span>端口: ' + (v.port || '--') + '</span>';
                            html += '<span>显存: ' + (v.required_memory || '--') + '</span>';
                            html += '</div>';
                            html += '<div class="aios-model-actions">';
                            if (!v.running) {
                                html += '<button class="aios-btn aios-btn-sm aios-btn-success" onclick="AiosManager.modelSwitch.startModel(\'' + escapeHtml(v.name) + '\')">启动</button>';
                            }
                            if (!v.is_current && v.path_exists) {
                                html += '<button class="aios-btn aios-btn-sm aios-btn-primary" onclick="AiosManager.modelSwitch.switchModel(\'' + escapeHtml(v.name) + '\')">切换</button>';
                            }
                            if (v.running && !v.is_current) {
                                html += '<button class="aios-btn aios-btn-sm aios-btn-warning" onclick="AiosManager.modelSwitch.stopModel(\'' + escapeHtml(v.name) + '\')">停止</button>';
                            }
                            html += '</div></div>';
                        });
                        html += '</div>';
                    });
                    document.getElementById('aios-models-container').innerHTML = html;

                    AiosManager.modelSwitch._allModels = allModels;
                    var select = document.getElementById('aios-quick-switch-model');
                    if (select) {
                        var currentVal = select.value;
                        select.innerHTML = '<option value="">选择模型...</option>';
                        allModels.forEach(function(m) {
                            var opt = document.createElement('option');
                            opt.value = m.name;
                            opt.textContent = m.name + (m.running ? ' (运行中)' : '') + (m.is_current ? ' ★' : '');
                            select.appendChild(opt);
                        });
                        if (currentVal && allModels.some(function(m) { return m.name === currentVal; })) {
                            select.value = currentVal;
                        }
                    }
                }).catch(function(err) {
                    document.getElementById('aios-models-container').innerHTML = '<div class="aios-error">加载失败: ' + escapeHtml(err.message) + '</div>';
                });

                adminFetch('/api/model-switch/switch-status').then(function(r) { return r.json(); }).then(function(data) {
                    var content = document.getElementById('aios-switch-status-content');
                    if (data && data.is_switching) {
                        content.innerHTML = '<div class="aios-switching">切换进行中: ' + escapeHtml(data.session.target_model || '--') + '</div>';
                    } else if (data && data.session) {
                        content.innerHTML = '<div>最近切换: ' + escapeHtml(data.session.target_model || '--') + ' (' + (data.session.completed_successfully ? '成功' : '失败') + ')</div>';
                    } else {
                        content.innerHTML = '无进行中的切换';
                    }
                });
            },

            quickSwitch: function() {
                var modelName = document.getElementById('aios-quick-switch-model').value;
                var engineType = document.getElementById('aios-quick-switch-engine').value;
                var port = parseInt(document.getElementById('aios-quick-switch-port').value) || 8000;
                if (!modelName) { alert('请选择目标模型'); return; }
                if (!confirm('确定切换到模型 ' + modelName + ' (引擎: ' + engineType + ')?')) return;
                adminFetch('/api/model-switch/switch', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ modelName: modelName, engineType: engineType, port: port })
                }).then(function(r) { return r.json(); }).then(function(data) {
                    if (data.success) {
                        alert('模型切换已启动: ' + modelName);
                        setTimeout(function() { AiosManager.modelSwitch.refresh(); }, 3000);
                    } else {
                        alert('切换失败: ' + (data.error || '未知错误'));
                    }
                }).catch(function(err) {
                    alert('请求失败: ' + err.message);
                });
            },

            quickSwitchEngine: function() {
                var modelName = document.getElementById('aios-quick-switch-model').value;
                var engineType = document.getElementById('aios-quick-switch-engine').value;
                var port = parseInt(document.getElementById('aios-quick-switch-port').value) || 8000;
                if (!modelName) { alert('请选择模型'); return; }
                if (!confirm('确定将模型 ' + modelName + ' 切换到引擎 ' + engineType + '?')) return;
                adminFetch('/api/engine/switch', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ model_name: modelName, engine_type: engineType, port: port })
                }).then(function(r) { return r.json(); }).then(function(data) {
                    if (data.success) {
                        alert('引擎切换已启动: ' + engineType);
                        setTimeout(function() { AiosManager.modelSwitch.refresh(); }, 3000);
                    } else {
                        alert('引擎切换失败: ' + (data.error || '未知错误'));
                    }
                }).catch(function(err) {
                    alert('请求失败: ' + err.message);
                });
            },

            switchModel: function(modelName) {
                if (!confirm('确定切换到模型 ' + modelName + '?')) return;
                adminFetch('/api/model-switch/switch', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ modelName: modelName })
                }).then(function(r) { return r.json(); }).then(function(data) {
                    if (data.success) {
                        alert('模型切换已启动: ' + modelName);
                        setTimeout(function() { AiosManager.modelSwitch.refresh(); }, 3000);
                    } else {
                        alert('切换失败: ' + (data.error || '未知错误'));
                    }
                }).catch(function(err) {
                    alert('请求失败: ' + err.message);
                });
            },

            startModel: function(modelName) {
                if (!confirm('确定启动模型 ' + modelName + '?')) return;
                adminFetch('/api/model-switch/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ modelName: modelName })
                }).then(function(r) { return r.json(); }).then(function(data) {
                    if (data.success) {
                        alert('模型启动已启动: ' + modelName);
                        setTimeout(function() { AiosManager.modelSwitch.refresh(); }, 5000);
                    } else {
                        alert('启动失败: ' + (data.error || '未知错误'));
                    }
                }).catch(function(err) {
                    alert('请求失败: ' + err.message);
                });
            },

            stopModel: function(modelName) {
                if (!confirm('确定停止模型 ' + modelName + '? 这将停止当前运行的推理服务。')) return;
                adminFetch('/api/model-switch/stop', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ modelName: modelName })
                }).then(function(r) { return r.json(); }).then(function(data) {
                    if (data.success) {
                        showToast('模型停止已启动: ' + modelName, 'success');
                        setTimeout(function() { AiosManager.modelSwitch.refresh(); }, 5000);
                    } else {
                        showToast('停止失败: ' + (data.error || '未知错误'), 'error');
                    }
                }).catch(function(err) {
                    showToast('请求失败: ' + err.message, 'error');
                });
            }
        },

        engine: {
            refresh: function() {
                adminFetch('/api/engine/status').then(function(r) {
                    if (r.status === 401) { promptForToken(); return null; }
                    return r.json();
                }).then(function(data) {
                    var content = document.getElementById('aios-engine-status-content');
                    var vllmStatus = document.getElementById('aios-engine-vllm-status');
                    var sglangStatus = document.getElementById('aios-engine-sglang-status');
                    var llamacppStatus = document.getElementById('aios-engine-llamacpp-status');

                    var engineStatuses = { vllm: null, sglang: null, llamacpp: null };

                    if (data && data.data) {
                        var d = data.data;
                        content.innerHTML = '<div class="aios-engine-info">';
                        content.innerHTML += '<div>引擎模式: ' + escapeHtml(d.engine_manager_mode || '--') + '</div>';
                        content.innerHTML += '<div>运行中服务: ' + (d.active_count || 0) + '</div>';
                        if (d.services) {
                            content.innerHTML += '<table class="aios-table"><thead><tr><th>服务</th><th>状态</th><th>端口</th><th>引擎</th><th>模型</th></tr></thead><tbody>';
                            d.services.forEach(function(s) {
                                content.innerHTML += '<tr><td>' + escapeHtml(s.name || '--') + '</td><td>' + escapeHtml(s.status || '--') + '</td><td>' + (s.port || '--') + '</td><td>' + escapeHtml(s.engine_type || '--') + '</td><td>' + escapeHtml(s.model || '--') + '</td></tr>';
                                if (s.engine_type && engineStatuses.hasOwnProperty(s.engine_type)) {
                                    engineStatuses[s.engine_type] = s;
                                }
                            });
                            content.innerHTML += '</tbody></table>';
                        }
                        content.innerHTML += '</div>';
                    } else {
                        content.innerHTML = '<div class="aios-empty">无引擎数据</div>';
                    }

                    var engineCards = document.querySelectorAll('.aios-engine-card');
                    engineCards.forEach(function(card) {
                        card.classList.remove('aios-engine-running', 'aios-engine-stopped');
                    });

                    Object.keys(engineStatuses).forEach(function(eng) {
                        var el = document.getElementById('aios-engine-' + eng + '-status');
                        var card = el ? el.closest('.aios-engine-card') : null;
                        if (engineStatuses[eng] && engineStatuses[eng].status === 'running') {
                            el.textContent = '运行中 (端口: ' + (engineStatuses[eng].port || '--') + ')';
                            el.className = 'aios-engine-card-status aios-engine-running-text';
                            if (card) card.classList.add('aios-engine-running');
                        } else {
                            el.textContent = '未运行';
                            el.className = 'aios-engine-card-status aios-engine-stopped-text';
                            if (card) card.classList.add('aios-engine-stopped');
                        }
                    });
                });

                adminFetch('/api/engine/config').then(function(r) { return r.json(); }).then(function(data) {
                    var content = document.getElementById('aios-engine-config-content');
                    if (data && data.data) {
                        var d = data.data;
                        content.innerHTML = '<div class="aios-engine-config-info">';
                        content.innerHTML += '<div>默认引擎: ' + escapeHtml(d.default_engine || '--') + '</div>';
                        content.innerHTML += '<div>引擎管理模式: ' + escapeHtml(d.engine_manager_mode || '--') + '</div>';
                        if (d.vllm) content.innerHTML += '<pre>' + escapeHtml(JSON.stringify(d.vllm, null, 2)) + '</pre>';
                        if (d.sglang) content.innerHTML += '<pre>sglang: ' + escapeHtml(JSON.stringify(d.sglang, null, 2)) + '</pre>';
                        content.innerHTML += '</div>';
                    } else {
                        content.innerHTML = '<div class="aios-empty">无配置数据</div>';
                    }
                });

                adminFetch('/api/model-switch/aggregated').then(function(r) {
                    if (r.status === 401) return null;
                    return r.json();
                }).then(function(data) {
                    var select = document.getElementById('aios-engine-switch-model');
                    if (!select) return;
                    var currentVal = select.value;
                    select.innerHTML = '<option value="">选择模型...</option>';
                    if (data && data.data && data.data.groups) {
                        data.data.groups.forEach(function(group) {
                            group.variants.forEach(function(v) {
                                var opt = document.createElement('option');
                                opt.value = v.name;
                                opt.textContent = v.name + (v.running ? ' (运行中)' : '') + (v.is_current ? ' ★' : '');
                                select.appendChild(opt);
                            });
                        });
                    }
                    if (currentVal) select.value = currentVal;
                });
            },

            switchEngine: function() {
                var modelName = document.getElementById('aios-engine-switch-model').value;
                var engineType = document.getElementById('aios-engine-switch-type').value;
                var port = parseInt(document.getElementById('aios-engine-switch-port').value) || 8000;
                if (!modelName) { alert('请选择模型'); return; }
                if (!confirm('确定将模型 ' + modelName + ' 切换到引擎 ' + engineType + ' (端口: ' + port + ')?')) return;
                adminFetch('/api/engine/switch', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ model_name: modelName, engine_type: engineType, port: port })
                }).then(function(r) { return r.json(); }).then(function(data) {
                    if (data.success) {
                        alert('引擎切换已启动: ' + engineType);
                        setTimeout(function() { AiosManager.engine.refresh(); }, 3000);
                    } else {
                        alert('引擎切换失败: ' + (data.error || '未知错误'));
                    }
                }).catch(function(err) {
                    alert('请求失败: ' + err.message);
                });
            }
        },

        config: {
            _globalConfig: null,
            _vllmConfig: null,

            refresh: function() {
                adminFetch('/api/config/global').then(function(r) {
                    if (r.status === 401) { promptForToken(); return null; }
                    return r.json();
                }).then(function(data) {
                    if (data && data.data) {
                        AiosManager.config._globalConfig = data.data;
                        var form = document.getElementById('aios-global-config-form');
                        form.innerHTML = '';
                        var cfg = data.data.config || data.data;
                        Object.keys(cfg).forEach(function(key) {
                            var val = cfg[key];
                            if (typeof val === 'object' && val !== null) {
                                form.innerHTML += '<div class="aios-config-field"><label>' + escapeHtml(key) + '</label><textarea class="aios-textarea" name="' + escapeHtml(key) + '">' + escapeHtml(JSON.stringify(val, null, 2)) + '</textarea></div>';
                            } else {
                                form.innerHTML += '<div class="aios-config-field"><label>' + escapeHtml(key) + '</label><input type="text" class="aios-input" name="' + escapeHtml(key) + '" value="' + escapeHtml(val) + '"></div>';
                            }
                        });
                    }
                });

                adminFetch('/api/config/vllm-default').then(function(r) { return r.json(); }).then(function(data) {
                    if (data && data.data) {
                        AiosManager.config._vllmConfig = data.data;
                        var form = document.getElementById('aios-vllm-config-form');
                        form.innerHTML = '';
                        var cfg = data.data;
                        Object.keys(cfg).forEach(function(key) {
                            var val = cfg[key];
                            form.innerHTML += '<div class="aios-config-field"><label>' + escapeHtml(key) + '</label><input type="number" step="any" class="aios-input" name="' + escapeHtml(key) + '" value="' + escapeHtml(val) + '"></div>';
                        });
                    }
                });

                adminFetch('/api/config/default-model').then(function(r) { return r.json(); }).then(function(data) {
                    var info = document.getElementById('aios-current-default-model');
                    if (data && data.data && data.data.default_model) {
                        info.textContent = '当前默认模型: ' + data.data.default_model;
                        document.getElementById('aios-default-model-input').value = data.data.default_model;
                    } else {
                        info.textContent = '当前默认模型: 未设置';
                    }
                });
            },

            save: function() {
                var globalForm = document.getElementById('aios-global-config-form');
                var formData = {};
                var inputs = globalForm.querySelectorAll('input, textarea');
                inputs.forEach(function(input) {
                    var val = input.value;
                    try { val = JSON.parse(val); } catch(e) {}
                    formData[input.name] = val;
                });

                adminFetch('/api/config/global', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(formData)
                }).then(function(r) { return r.json(); }).then(function(data) {
                    if (data.success) {
                        alert('配置已保存');
                    } else {
                        alert('保存失败: ' + (data.error || '未知错误'));
                    }
                });
            },

            setDefaultModel: function() {
                var model = document.getElementById('aios-default-model-input').value.trim();
                if (!model) { alert('请输入模型名称'); return; }
                adminFetch('/api/config/default-model', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ model: model })
                }).then(function(r) { return r.json(); }).then(function(data) {
                    if (data.success) {
                        alert('默认模型已设置: ' + model);
                        AiosManager.config.refresh();
                    } else {
                        alert('设置失败: ' + (data.error || '未知错误'));
                    }
                });
            },

            clearDefaultModel: function() {
                adminFetch('/api/config/default-model', { method: 'DELETE' }).then(function(r) { return r.json(); }).then(function(data) {
                    if (data.success) {
                        alert('默认模型已清除');
                        AiosManager.config.refresh();
                    } else {
                        alert('清除失败');
                    }
                });
            }
        },

        health: {
            _healthHistory: [],

            initChart: function() {
                var canvas = document.getElementById('aios-health-history-chart');
                if (canvas) {
                    canvas.width = canvas.parentElement.offsetWidth - 40;
                    canvas.height = 150;
                }
            },

            refresh: function() {
                adminFetch('/api/health/alert').then(function(r) {
                    if (r.status === 401) { promptForToken(); return null; }
                    return r.json();
                }).then(function(data) {
                    if (data && data.data) {
                        var d = data.data;
                        var score = d.health_score || 0;
                        var circle = document.getElementById('aios-health-score-circle');
                        circle.style.borderColor = score > 80 ? '#22c55e' : score > 50 ? '#f59e0b' : '#ef4444';
                        document.getElementById('aios-health-score-value').textContent = score;

                        var statusContent = document.getElementById('aios-health-status-content');
                        statusContent.innerHTML = '<div class="aios-status-' + (d.status || 'unknown') + '">' + escapeHtml(d.status || '未知') + '</div>';
                        if (d.alert_reasons && d.alert_reasons.length > 0) {
                            var alertsHtml = '<ul class="aios-alert-list">';
                            d.alert_reasons.forEach(function(reason) {
                                alertsHtml += '<li class="aios-alert-item">' + escapeHtml(reason) + '</li>';
                            });
                            alertsHtml += '</ul>';
                            document.getElementById('aios-alerts-container').innerHTML = alertsHtml;
                        } else {
                            document.getElementById('aios-alerts-container').innerHTML = '<div class="aios-empty">无告警</div>';
                        }
                    }
                });

                adminFetch('/api/health/history').then(function(r) { return r.json(); }).then(function(data) {
                    if (data && data.data && data.data.length > 1) {
                        AiosManager.health._healthHistory = data.data;
                        var scores = data.data.map(function(h) { return h.health_score || 0; });
                        var labels = data.data.map(function(h) { return new Date(h.timestamp).toLocaleTimeString(); });
                        drawLineChart('aios-health-history-chart', [
                            { label: '健康评分', data: scores }
                        ], labels);
                    }
                });

                adminFetch('/api/health/system-status').then(function(r) {
                    if (!r.ok) return null;
                    return r.json();
                }).then(function(result) {
                    var data = result && result.data ? result.data : null;
                    if (data && data.cpu) {
                        var cpuP = data.cpu.percent || 0;
                        document.getElementById('aios-cpu-util').textContent = cpuP + '%';
                        document.getElementById('aios-cpu-bar').style.width = cpuP + '%';
                        document.getElementById('aios-cpu-bar').className = 'aios-progress-fill ' + (cpuP > 80 ? 'aios-danger' : cpuP > 50 ? 'aios-warning' : 'aios-success');

                        var memP = data.memory.percent || 0;
                        var memUsed = formatBytes(data.memory.used_mb * 1024 * 1024);
                        var memTotal = formatBytes(data.memory.total_mb * 1024 * 1024);
                        document.getElementById('aios-mem-util').textContent = memUsed + ' / ' + memTotal + ' (' + memP + '%)';
                        document.getElementById('aios-mem-bar').style.width = memP + '%';
                        document.getElementById('aios-mem-bar').className = 'aios-progress-fill ' + (memP > 90 ? 'aios-danger' : memP > 70 ? 'aios-warning' : 'aios-success');

                        var diskP = data.disk.percent || 0;
                        document.getElementById('aios-disk-util').textContent = data.disk.used_gb + 'GB / ' + data.disk.total_gb + 'GB (' + diskP + '%)';
                        document.getElementById('aios-disk-bar').style.width = diskP + '%';
                        document.getElementById('aios-disk-bar').className = 'aios-progress-fill ' + (diskP > 90 ? 'aios-danger' : diskP > 70 ? 'aios-warning' : 'aios-success');
                    }
                });
            },

            runCheck: function() {
                adminFetch('/api/health/check', { method: 'POST' }).then(function(r) { return r.json(); }).then(function(data) {
                    if (data.success) {
                        alert('健康检查完成');
                        AiosManager.health.refresh();
                    } else {
                        alert('检查失败: ' + (data.error || '未知错误'));
                    }
                });
            }
        },

        ratelimit: {
            refresh: function() {
                adminFetch('/api/ratelimit/status').then(function(r) {
                    if (r.status === 401) { promptForToken(); return null; }
                    return r.json();
                }).then(function(data) {
                    var content = document.getElementById('aios-queue-content');
                    if (data && data.data) {
                        var d = data.data;
                        var html = '<table class="aios-table"><thead><tr><th>模型</th><th>活跃请求</th><th>并发限制</th><th>可接受</th></tr></thead><tbody>';
                        if (typeof d === 'object') {
                            Object.keys(d).forEach(function(model) {
                                var info = d[model];
                                html += '<tr><td>' + escapeHtml(model) + '</td><td>' + (info.active_requests || 0) + '</td><td>' + (info.concurrency_limit || '--') + '</td><td>' + (info.can_accept ? '是' : '否') + '</td></tr>';
                            });
                        }
                        html += '</tbody></table>';
                        content.innerHTML = html;
                    } else {
                        content.innerHTML = '<div class="aios-empty">无队列数据</div>';
                    }
                });

                adminFetch('/api/ratelimit/config').then(function(r) { return r.json(); }).then(function(data) {
                    var form = document.getElementById('aios-ratelimit-config-form');
                    if (data && data.data) {
                        var cfg = data.data;
                        form.innerHTML = '';
                        var fields = ['ip_qps_limit', 'ip_qps_window_seconds', 'concurrency_limit', 'queue_timeout_seconds'];
                        fields.forEach(function(field) {
                            if (cfg[field] !== undefined) {
                                form.innerHTML += '<div class="aios-config-field"><label>' + escapeHtml(field) + '</label><input type="number" class="aios-input" name="' + escapeHtml(field) + '" value="' + cfg[field] + '"></div>';
                            }
                        });
                        if (cfg.rate_limited_paths) {
                            form.innerHTML += '<div class="aios-config-field"><label>限流路径</label><textarea class="aios-textarea" name="rate_limited_paths">' + escapeHtml(JSON.stringify(cfg.rate_limited_paths, null, 2)) + '</textarea></div>';
                        }
                    } else {
                        form.innerHTML = '<div class="aios-empty">无配置数据</div>';
                    }
                });

                adminFetch('/api/ratelimit/stats').then(function(r) { return r.json(); }).then(function(data) {
                    var content = document.getElementById('aios-ratelimit-stats-content');
                    if (data && data.data) {
                        var d = data.data;
                        content.innerHTML = '<div class="aios-stats-grid">';
                        content.innerHTML += '<div class="aios-stat"><span class="aios-stat-label">总拒绝数</span><span class="aios-stat-value">' + (d.total_rejected || 0) + '</span></div>';
                        content.innerHTML += '<div class="aios-stat"><span class="aios-stat-label">429计数</span><span class="aios-stat-value">' + (d.recent_429_count || 0) + '</span></div>';
                        content.innerHTML += '<div class="aios-stat"><span class="aios-stat-label">队列深度</span><span class="aios-stat-value">' + (d.current_queue_depth || 0) + '</span></div>';
                        content.innerHTML += '</div>';
                    } else {
                        content.innerHTML = '<div class="aios-empty">无统计数据</div>';
                    }
                });
            },

            saveConfig: function() {
                var form = document.getElementById('aios-ratelimit-config-form');
                var formData = {};
                var inputs = form.querySelectorAll('input, textarea');
                inputs.forEach(function(input) {
                    var val = input.value;
                    try { val = JSON.parse(val); } catch(e) {}
                    formData[input.name] = val;
                });

                adminFetch('/api/ratelimit/config', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(formData)
                }).then(function(r) { return r.json(); }).then(function(data) {
                    if (data.success) {
                        alert('限流配置已保存');
                    } else {
                        alert('保存失败: ' + (data.error || '未知错误'));
                    }
                });
            }
        }
    };

    function loadData(sectionId) {
        var loaders = {
            'aios-gpu': function() { AiosManager.gpu.refresh(); },
            'aios-switch': function() { AiosManager.modelSwitch.refresh(); },
            'aios-engine': function() { AiosManager.engine.refresh(); },
            'aios-config': function() { AiosManager.config.refresh(); },
            'aios-health': function() { AiosManager.health.refresh(); },
            'aios-ratelimit': function() { AiosManager.ratelimit.refresh(); },
        };
        var loader = loaders[sectionId];
        if (loader) loader();
    }

    function tryInit() {
        _logger('Initializing...');
        if (!checkDOMAndInit()) {
            setupObserver();
            startPolling();
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', tryInit);
    } else {
        tryInit();
    }
})();
