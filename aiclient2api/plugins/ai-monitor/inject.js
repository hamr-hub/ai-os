(function() {
    'use strict';

    if (window.__aiMonitorPanelInitialized) return;
    window.__aiMonitorPanelInitialized = true;

    var PANEL_ID = 'ai-monitor-panel';
    var TOGGLE_ID = 'ai-monitor-toggle';
    var REFRESH_MS = 5000;
    var _refreshTimer = null;
    var _expanded = false;
    var _switching = false;

    var ENGINE_LABELS = {
        vllm: 'vLLM',
        sglang: 'SGLang',
        llamacpp: 'llama.cpp'
    };

    var ENGINE_COLORS = {
        vllm: '#3b82f6',
        sglang: '#22c55e',
        llamacpp: '#f59e0b'
    };

    function esc(str) {
        return String(str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
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

    function showToast(msg, type) {
        var container = document.getElementById('ai-monitor-toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'ai-monitor-toast-container';
            document.body.appendChild(container);
        }
        var toast = document.createElement('div');
        toast.className = 'aim-toast aim-toast-' + (type || 'info');
        toast.innerHTML = '<span>' + esc(msg) + '</span><button class="aim-toast-close" onclick="this.parentElement.remove()">&times;</button>';
        container.appendChild(toast);
        setTimeout(function() { if (toast.parentElement) toast.remove(); }, 4000);
    }

    function createPanel() {
        if (document.getElementById(PANEL_ID)) return;

        var toggle = document.createElement('div');
        toggle.id = TOGGLE_ID;
        toggle.innerHTML = '<span class="aim-toggle-icon"><i class="fas fa-bolt"></i></span><span class="aim-toggle-label">AI Monitor</span>';
        toggle.addEventListener('click', togglePanel);
        document.body.appendChild(toggle);

        var panel = document.createElement('div');
        panel.id = PANEL_ID;
        panel.innerHTML = '\
<div class="aim-panel-header">\
    <span class="aim-panel-title">AI Monitor</span>\
    <div class="aim-panel-header-actions">\
        <button class="aim-btn aim-btn-sm" id="aim-refresh-btn" onclick="window.__aiMonitorRefresh()"><i class="fas fa-sync-alt"></i> 刷新</button>
        <button class="aim-btn aim-btn-sm aim-btn-collapse" onclick="window.__aiMonitorToggle()"><i class="fas fa-times"></i></button>\
    </div>\
</div>\
<div class="aim-panel-body">\
    <div class="aim-section">\
        <div class="aim-section-title">当前引擎</div>\
        <div class="aim-engine-cards" id="aim-engine-cards">\
            <div class="aim-engine-card" data-engine="vllm">\
                <div class="aim-engine-indicator" id="aim-engine-vllm-dot"></div>\
                <div class="aim-engine-info">\
                    <div class="aim-engine-name">vLLM</div>\
                    <div class="aim-engine-detail" id="aim-engine-vllm-detail">--</div>\
                </div>\
            </div>\
            <div class="aim-engine-card" data-engine="sglang">\
                <div class="aim-engine-indicator" id="aim-engine-sglang-dot"></div>\
                <div class="aim-engine-info">\
                    <div class="aim-engine-name">SGLang</div>\
                    <div class="aim-engine-detail" id="aim-engine-sglang-detail">--</div>\
                </div>\
            </div>\
            <div class="aim-engine-card" data-engine="llamacpp">\
                <div class="aim-engine-indicator" id="aim-engine-llamacpp-dot"></div>\
                <div class="aim-engine-info">\
                    <div class="aim-engine-name">llama.cpp</div>\
                    <div class="aim-engine-detail" id="aim-engine-llamacpp-detail">--</div>\
                </div>\
            </div>\
        </div>\
    </div>\
    <div class="aim-section">\
        <div class="aim-section-title">运行中的模型</div>\
        <div id="aim-running-models" class="aim-running-models">\
            <div class="aim-empty">加载中...</div>\
        </div>\
    </div>\
    <div class="aim-section">\
        <div class="aim-section-title">切换模型</div>\
        <div class="aim-switch-form">\
            <select id="aim-switch-model-select" class="aim-select">\
                <option value="">选择模型...</option>\
            </select>\
            <select id="aim-switch-engine-select" class="aim-select">\
                <option value="vllm">vLLM</option>\
                <option value="sglang">SGLang</option>\
                <option value="llamacpp">llama.cpp</option>\
            </select>\
            <button class="aim-btn aim-btn-primary aim-btn-block" id="aim-switch-model-btn" onclick="window.__aiMonitorSwitchModel()"><i class="fas fa-exchange-alt"></i> 切换模型</button>\
        </div>\
    </div>\
    <div class="aim-section">\
        <div class="aim-section-title">切换引擎</div>\
        <div class="aim-engine-switch">\
            <div class="aim-engine-switch-row">\
                <button class="aim-btn aim-btn-engine" data-engine="vllm" onclick="window.__aiMonitorSwitchEngine(\'vllm\')">\
                    <span class="aim-engine-dot" style="background:#3b82f6"></span> vLLM\
                </button>\
                <button class="aim-btn aim-btn-engine" data-engine="sglang" onclick="window.__aiMonitorSwitchEngine(\'sglang\')">\
                    <span class="aim-engine-dot" style="background:#22c55e"></span> SGLang\
                </button>\
                <button class="aim-btn aim-btn-engine" data-engine="llamacpp" onclick="window.__aiMonitorSwitchEngine(\'llamacpp\')">\
                    <span class="aim-engine-dot" style="background:#f59e0b"></span> llama.cpp\
                </button>\
            </div>\
        </div>\
    </div>\
</div>';
        document.body.appendChild(panel);
    }

    function togglePanel() {
        var panel = document.getElementById(PANEL_ID);
        var toggle = document.getElementById(TOGGLE_ID);
        _expanded = !_expanded;
        if (_expanded) {
            panel.classList.add('aim-panel-open');
            toggle.classList.add('aim-toggle-active');
            refresh();
            startAutoRefresh();
        } else {
            panel.classList.remove('aim-panel-open');
            toggle.classList.remove('aim-toggle-active');
            stopAutoRefresh();
        }
    }

    function startAutoRefresh() {
        stopAutoRefresh();
        _refreshTimer = setInterval(function() { refresh(); }, REFRESH_MS);
    }

    function stopAutoRefresh() {
        if (_refreshTimer) { clearInterval(_refreshTimer); _refreshTimer = null; }
    }

    function refresh() {
        adminFetch('/api/ai-monitor/status').then(function(r) {
            if (r.status === 401) return null;
            return r.json();
        }).then(function(data) {
            if (!data || !data.data) return;
            updateEngineCards(data.data);
            updateRunningModels(data.data);
        }).catch(function() {});

        adminFetch('/api/ai-monitor/models').then(function(r) {
            if (r.status === 401) return null;
            return r.json();
        }).then(function(data) {
            if (!data || !data.data) return;
            updateModelSelect(data);
        }).catch(function() {});
    }

    function updateEngineCards(data) {
        var engines = { vllm: null, sglang: null, llamacpp: null };

        if (data.engineStatus && data.engineStatus.services) {
            data.engineStatus.services.forEach(function(s) {
                if (engines.hasOwnProperty(s.engine_type)) {
                    engines[s.engine_type] = s;
                }
            });
        }

        Object.keys(engines).forEach(function(type) {
            var dot = document.getElementById('aim-engine-' + type + '-dot');
            var detail = document.getElementById('aim-engine-' + type + '-detail');
            var card = dot ? dot.closest('.aim-engine-card') : null;
            var service = engines[type];

            if (service && service.status === 'running') {
                dot.className = 'aim-engine-indicator aim-indicator-running';
                detail.textContent = '端口 ' + (service.port || '--') + ' · ' + esc(service.model || '--');
                if (card) {
                    card.classList.add('aim-engine-active');
                    card.classList.remove('aim-engine-inactive');
                }
            } else {
                dot.className = 'aim-engine-indicator aim-indicator-stopped';
                detail.textContent = '未运行';
                if (card) {
                    card.classList.remove('aim-engine-active');
                    card.classList.add('aim-engine-inactive');
                }
            }
        });

        var toggle = document.getElementById(TOGGLE_ID);
        if (toggle) {
            var currentEngine = data.currentEngine || '--';
            var label = ENGINE_LABELS[currentEngine] || currentEngine;
            toggle.querySelector('.aim-toggle-label').textContent = label;
            toggle.style.borderColor = ENGINE_COLORS[currentEngine] || '#6366f1';
        }
    }

    function updateRunningModels(data) {
        var container = document.getElementById('aim-running-models');
        if (!container) return;

        var models = data.runningModels || [];
        var currentModel = data.currentModel;

        if (models.length === 0) {
            container.innerHTML = '<div class="aim-empty">无运行中的模型</div>';
            return;
        }

        var html = '';
        models.forEach(function(m) {
            var isCurrent = m.name === currentModel || m.isCurrent;
            html += '<div class="aim-model-item' + (isCurrent ? ' aim-model-current' : '') + '">';
            html += '<div class="aim-model-row">';
            html += '<span class="aim-model-name">' + esc(m.name) + '</span>';
            if (isCurrent) html += '<span class="aim-model-badge">当前</span>';
            html += '</div>';
            html += '<div class="aim-model-meta">';
            html += '<span class="aim-meta-engine" style="color:' + (ENGINE_COLORS[m.engine] || '#8b949e') + '">' + esc(ENGINE_LABELS[m.engine] || m.engine) + '</span>';
            if (m.port) html += '<span class="aim-meta-port">:' + m.port + '</span>';
            html += '</div>';
            html += '</div>';
        });
        container.innerHTML = html;
    }

    function updateModelSelect(data) {
        var select = document.getElementById('aim-switch-model-select');
        if (!select) return;

        var currentVal = select.value;
        var currentModel = data.currentModel || null;
        select.innerHTML = '<option value="">选择模型...</option>';

        var models = data.data || [];
        models.forEach(function(m) {
            var opt = document.createElement('option');
            opt.value = m.name;
            var suffix = '';
            if (m.running) suffix += ' (运行中)';
            if (m.name === currentModel || m.isCurrent) suffix += ' ★';
            opt.textContent = m.name + suffix;
            select.appendChild(opt);
        });

        if (currentVal) select.value = currentVal;

        if (currentModel) {
            var engineSelect = document.getElementById('aim-switch-engine-select');
            if (engineSelect) {
                var currentM = models.find(function(m) { return m.name === currentModel; });
                if (currentM && currentM.engine) {
                    engineSelect.value = currentM.engine;
                }
            }
        }
    }

    function switchModel() {
        if (_switching) return;
        var modelName = document.getElementById('aim-switch-model-select').value;
        var engineType = document.getElementById('aim-switch-engine-select').value;
        if (!modelName) { showToast('请选择目标模型', 'warning'); return; }

        _switching = true;
        var btn = document.getElementById('aim-switch-model-btn');
        btn.textContent = '切换中...';
        btn.disabled = true;

        adminFetch('/api/ai-monitor/switch-model', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model_name: modelName, engine_type: engineType })
        }).then(function(r) { return r.json(); }).then(function(data) {
            if (data.success) {
                showToast('模型切换已启动: ' + modelName, 'success');
                setTimeout(function() { refresh(); }, 3000);
            } else {
                showToast('切换失败: ' + (data.error || data.data?.detail || '未知错误'), 'error');
            }
        }).catch(function(err) {
            showToast('请求失败: ' + err.message, 'error');
        }).finally(function() {
            _switching = false;
            btn.textContent = '切换模型';
            btn.disabled = false;
        });
    }

    function switchEngine(engineType) {
        if (_switching) return;
        var modelName = document.getElementById('aim-switch-model-select').value;
        if (!modelName) {
            var statusEl = document.getElementById('aim-running-models');
            var currentEl = statusEl ? statusEl.querySelector('.aim-model-current .aim-model-name') : null;
            if (currentEl) {
                modelName = currentEl.textContent;
            }
        }
        if (!modelName) { showToast('请先选择模型或确保有运行中的模型', 'warning'); return; }

        _switching = true;
        showToast('正在切换引擎到 ' + (ENGINE_LABELS[engineType] || engineType) + '...', 'info');

        adminFetch('/api/ai-monitor/switch-engine', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model_name: modelName, engine_type: engineType })
        }).then(function(r) { return r.json(); }).then(function(data) {
            if (data.success) {
                showToast('引擎切换已启动: ' + (ENGINE_LABELS[engineType] || engineType), 'success');
                setTimeout(function() { refresh(); }, 3000);
            } else {
                showToast('引擎切换失败: ' + (data.error || data.data?.detail || '未知错误'), 'error');
            }
        }).catch(function(err) {
            showToast('请求失败: ' + err.message, 'error');
        }).finally(function() {
            _switching = false;
        });
    }

    window.__aiMonitorToggle = togglePanel;
    window.__aiMonitorRefresh = refresh;
    window.__aiMonitorSwitchModel = switchModel;
    window.__aiMonitorSwitchEngine = switchEngine;

    function injectStyles() {
        if (document.getElementById('ai-monitor-styles')) return;
        var link = document.createElement('link');
        link.id = 'ai-monitor-styles';
        link.rel = 'stylesheet';
        link.href = '/plugins/ai-monitor/styles.css';
        document.head.appendChild(link);

        if (!document.querySelector('link[href*="font-awesome"]')) {
            var fa = document.createElement('link');
            fa.rel = 'stylesheet';
            fa.href = 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css';
            document.head.appendChild(fa);
        }
    }

    function init() {
        injectStyles();
        createPanel();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
