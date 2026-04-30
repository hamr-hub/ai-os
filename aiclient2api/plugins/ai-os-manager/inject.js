(function() {
    'use strict';

    var MENU_IDS = {
        gpu: 'nav-aios-gpu',
        switch: 'nav-aios-switch',
        engine: 'nav-aios-engine',
        config: 'nav-aios-config',
        health: 'nav-aios-health',
        ratelimit: 'nav-aios-ratelimit',
    };
    var STYLE_ID = 'aios-manager-styles';

    var sectionHTML = '\
<div id="aios-gpu" class="section" data-section="aios-gpu" style="display: none;">\
    <div class="section-header"><h2>GPU监控</h2></div>\
    <div class="card aios-status-card">\
        <div id="aios-gpu-content"><p>正在加载GPU数据...</p></div>\
    </div>\
</div>\
\
<div id="aios-switch" class="section" data-section="aios-switch" style="display: none;">\
    <div class="section-header"><h2>模型切换</h2></div>\
    <div class="card aios-status-card">\
        <div id="aios-switch-content"><p>正在加载模型数据...</p></div>\
    </div>\
</div>\
\
<div id="aios-engine" class="section" data-section="aios-engine" style="display: none;">\
    <div class="section-header"><h2>引擎管理</h2></div>\
    <div class="card aios-status-card">\
        <div id="aios-engine-content"><p>正在加载引擎数据...</p></div>\
    </div>\
</div>\
\
<div id="aios-config" class="section" data-section="aios-config" style="display: none;">\
    <div class="section-header"><h2>配置中心</h2></div>\
    <div class="card aios-status-card">\
        <div id="aios-config-content"><p>正在加载配置数据...</p></div>\
    </div>\
</div>\
\
<div id="aios-health" class="section" data-section="aios-health" style="display: none;">\
    <div class="section-header"><h2>健康运维</h2></div>\
    <div class="card aios-status-card">\
        <div id="aios-health-content"><p>正在加载健康数据...</p></div>\
    </div>\
</div>\
\
<div id="aios-ratelimit" class="section" data-section="aios-ratelimit" style="display: none;">\
    <div class="section-header"><h2>限流控制</h2></div>\
    <div class="card aios-status-card">\
        <div id="aios-ratelimit-content"><p>正在加载限流数据...</p></div>\
    </div>\
</div>';

    function injectStyles() {
        if (document.getElementById(STYLE_ID)) return true;
        var link = document.createElement('link');
        link.id = STYLE_ID; link.rel = 'stylesheet';
        link.href = '/plugins/ai-os-manager/styles.css';
        document.head.appendChild(link);
        return true;
    }

    function injectMenuItems() {
        var nav = document.querySelector('.sidebar-nav');
        if (!nav) return false;

        var items = [
            { id: MENU_IDS.gpu, section: 'aios-gpu', icon: 'fa-microchip', label: 'GPU监控' },
            { id: MENU_IDS.switch, section: 'aios-switch', icon: 'fa-exchange-alt', label: '模型切换' },
            { id: MENU_IDS.engine, section: 'aios-engine', icon: 'fa-bolt', label: '引擎管理' },
            { id: MENU_IDS.config, section: 'aios-config', icon: 'fa-cog', label: '配置中心' },
            { id: MENU_IDS.health, section: 'aios-health', icon: 'fa-heartbeat', label: '健康运维' },
            { id: MENU_IDS.ratelimit, section: 'aios-ratelimit', icon: 'fa-tachometer-alt', label: '限流控制' },
        ];

        var anchor = document.getElementById('nav-plugins');
        items.forEach(function(item) {
            if (document.getElementById(item.id)) return;
            var navItem = document.createElement('a');
            navItem.href = '#' + item.section;
            navItem.className = 'nav-item';
            navItem.id = item.id;
            navItem.dataset.section = item.section;
            navItem.innerHTML = '<i class="fas ' + item.icon + '" aria-hidden="true"></i> <span>' + item.label + '</span>';
            if (anchor) anchor.after(navItem);
            else nav.appendChild(navItem);
            anchor = navItem;
        });
        return true;
    }

    function injectSections() {
        var cc = document.getElementById('content-container');
        if (!cc) return false;
        if (document.getElementById('aios-gpu')) return true;
        cc.insertAdjacentHTML('beforeend', sectionHTML);
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
                loadData(sectionId);
            });
        });
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

    function loadData(sectionId) {
        var urlMap = {
            'aios-gpu': '/api/gpu-monitor/info',
            'aios-switch': '/api/model-switch/aggregated',
            'aios-engine': '/api/engine/status',
            'aios-config': '/api/config/global',
            'aios-health': '/api/health/alert',
            'aios-ratelimit': '/api/ratelimit/status',
        };
        var url = urlMap[sectionId];
        if (!url) return;
        var contentId = sectionId + '-content';
        var el = document.getElementById(contentId);
        if (!el) return;
        adminFetch(url).then(function(r) {
            if (r.status === 401) {
                el.innerHTML = '<p class="aios-error">需要管理员令牌，请点击右上角设置令牌</p>';
                promptForToken();
                return null;
            }
            return r.json();
        }).then(function(data) {
            if (!data) return;
            el.innerHTML = '<pre class="aios-data-pre">' + JSON.stringify(data, null, 2) + '</pre>';
        }).catch(function(err) {
            el.innerHTML = '<p class="aios-error">错误: ' + err.message + '</p>';
        });
    }

    function promptForToken() {
        var existing = getAdminToken();
        var token = window.prompt('请输入管理员令牌 (Admin Token):', existing);
        if (token) {
            try { localStorage.setItem('aios_admin_token', token); } catch(e) {}
        }
    }

    function init() {
        injectStyles();
        if (injectMenuItems() && injectSections()) {
            initNavigation();
        }
    }

    function tryInit() {
        if (document.querySelector('.sidebar-nav') && document.getElementById('content-container')) init();
        else setTimeout(tryInit, 500);
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', tryInit);
    else tryInit();
})();
