/**
 * GPU 监控与模型切换 - 菜单注入脚本
 * 
 * 在 aiclient2api 管理面板加载完成后，动态注入：
 * 1. Sidebar 菜单项
 * 2. 对应的 Section 内容
 * 3. CSS 样式
 */

(function() {
    'use strict';

    const PLUGIN_ID = 'gpu-monitor-switch';
    const MENU_ID = 'nav-gpu-monitor';
    const SECTION_ID = 'section-gpu-monitor';
    const STYLE_ID = 'gpu-monitor-styles';

    // 菜单配置
    const menuConfig = {
        id: MENU_ID,
        section: 'gpu-monitor',
        icon: 'fas fa-microchip',
        label: 'GPU 监控',
        insertAfter: 'nav-plugins',
    };

    // Section HTML 模板
    const sectionHTML = `
<div id="gpu-monitor" class="section" data-section="gpu-monitor" style="display: none;">
    <div class="section-header">
        <h2><i class="fas fa-microchip"></i> <span>GPU 监控与模型切换</span></h2>
    </div>
    
    <!-- GPU 状态卡片 -->
    <div class="card">
        <div class="card-header">
            <h3><i class="fas fa-desktop"></i> <span>GPU 状态</span></h3>
            <button class="btn btn-sm btn-primary" id="gpuRefreshBtn">
                <i class="fas fa-sync-alt"></i> <span>刷新</span>
            </button>
        </div>
        <div class="card-body">
            <div id="gpuStatusContent">
                <div class="loading-spinner">
                    <i class="fas fa-spinner fa-spin"></i>
                    <span>加载中...</span>
                </div>
            </div>
        </div>
    </div>

    <!-- 模型切换卡片 -->
    <div class="card" style="margin-top: 20px;">
        <div class="card-header">
            <h3><i class="fas fa-exchange-alt"></i> <span>模型切换</span></h3>
        </div>
        <div class="card-body">
            <div id="modelSwitchContent">
                <div class="loading-spinner">
                    <i class="fas fa-spinner fa-spin"></i>
                    <span>加载中...</span>
                </div>
            </div>
        </div>
    </div>
</div>
`;

    // 注入 CSS
    function injectStyles() {
        if (document.getElementById(STYLE_ID)) return true;

        const link = document.createElement('link');
        link.id = STYLE_ID;
        link.rel = 'stylesheet';
        link.href = '/plugins/gpu-monitor-switch/styles.css';
        document.head.appendChild(link);
        
        console.log(`[${PLUGIN_ID}] Styles injected`);
        return true;
    }

    // GPU 状态渲染
    function renderGPUStatus(data) {
        if (!data || data.length === 0) {
            return `
                <div class="empty-state">
                    <i class="fas fa-info-circle"></i>
                    <p>未检测到 GPU 设备</p>
                </div>
            `;
        }

        let html = '<div class="gpu-grid">';
        data.forEach(gpu => {
            const memUsed = gpu.memoryUsed ? (gpu.memoryUsed / 1024).toFixed(1) : '--';
            const memTotal = gpu.memoryTotal ? (gpu.memoryTotal / 1024).toFixed(1) : '--';
            const memPercent = gpu.memoryUsagePercent || 0;
            const gpuUtil = gpu.gpuUtilization || 0;
            const temp = gpu.temperature ?? '--';
            const power = gpu.powerDraw != null ? `${gpu.powerDraw.toFixed(1)}W` : '--';
            const powerLimit = gpu.powerLimit != null ? `${gpu.powerLimit.toFixed(1)}W` : '';

            html += `
                <div class="gpu-card">
                    <div class="gpu-header">
                        <div class="gpu-name">
                            <i class="fas fa-desktop"></i>
                            <span>#${gpu.index} ${gpu.name}</span>
                        </div>
                    </div>
                    <div class="gpu-metrics">
                        <div class="metric">
                            <div class="metric-label">GPU 使用率</div>
                            <div class="metric-value">${gpuUtil.toFixed(1)}%</div>
                            <div class="progress-bar">
                                <div class="progress-fill" style="width: ${gpuUtil}%; background: ${getMetricColor(gpuUtil)}"></div>
                            </div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">显存使用</div>
                            <div class="metric-value">${memUsed} GB / ${memTotal} GB</div>
                            <div class="progress-bar">
                                <div class="progress-fill" style="width: ${memPercent}%; background: ${getMetricColor(memPercent)}"></div>
                            </div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">温度</div>
                            <div class="metric-value">${temp}${temp !== '--' ? '°C' : ''}</div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">功耗</div>
                            <div class="metric-value">${power}${powerLimit ? ' / ' + powerLimit : ''}</div>
                        </div>
                    </div>
                </div>
            `;
        });
        html += '</div>';
        return html;
    }

    function getMetricColor(value) {
        if (value < 60) return '#10b981';
        if (value < 80) return '#f59e0b';
        return '#ef4444';
    }

    // 加载 GPU 数据
    async function loadGPUData() {
        const contentEl = document.getElementById('gpuStatusContent');
        if (!contentEl) return;

        contentEl.innerHTML = `
            <div class="loading-spinner">
                <i class="fas fa-spinner fa-spin"></i>
                <span>加载中...</span>
            </div>
        `;

        try {
            const response = await fetch('/api/gpu-monitor');
            const result = await response.json();

            if (result.success && result.data && result.data.length > 0) {
                contentEl.innerHTML = renderGPUStatus(result.data);
            } else {
                contentEl.innerHTML = `
                    <div class="empty-state">
                        <i class="fas fa-info-circle"></i>
                        <p>未检测到 GPU 设备</p>
                    </div>
                `;
            }
        } catch (error) {
            contentEl.innerHTML = `
                <div class="empty-state error">
                    <i class="fas fa-exclamation-triangle"></i>
                    <p>加载失败: ${error.message}</p>
                </div>
            `;
        }
    }

    // 渲染模型切换
    async function renderModels() {
        const contentEl = document.getElementById('modelSwitchContent');
        if (!contentEl) return;

        contentEl.innerHTML = `
            <div class="loading-spinner">
                <i class="fas fa-spinner fa-spin"></i>
                <span>加载中...</span>
            </div>
        `;

        try {
            const response = await fetch('/api/model-switch/providers');
            const result = await response.json();

            if (!result.success || !result.data || result.data.length === 0) {
                contentEl.innerHTML = `
                    <div class="empty-state">
                        <i class="fas fa-info-circle"></i>
                        <p>未找到 Provider 配置</p>
                    </div>
                `;
                return;
            }

            let html = '<div class="provider-list">';
            result.data.forEach(provider => {
                const statusClass = provider.isDisabled ? 'status-disabled' :
                    (provider.isHealthy ? 'status-healthy' : 'status-unhealthy');
                const statusText = provider.isDisabled ? '已禁用' :
                    (provider.isHealthy ? '健康' : '不健康');

                html += `
                    <div class="provider-item">
                        <div class="provider-header">
                            <div class="provider-name">${provider.customName}</div>
                            <span class="provider-status ${statusClass}">${statusText}</span>
                        </div>
                        <div class="provider-details">
                            <div class="detail-item">
                                <span class="detail-label">当前模型</span>
                                <span class="detail-value">${provider.currentModel}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">调用次数</span>
                                <span class="detail-value">${provider.usageCount || 0}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">错误次数</span>
                                <span class="detail-value">${provider.errorCount || 0}</span>
                            </div>
                        </div>
                        <div class="provider-actions">
                            <input type="text" class="model-input" 
                                   id="model-input-${provider.uuid}" 
                                   placeholder="输入新模型名称"
                                   value="${provider.currentModel}">
                            <button class="btn btn-primary" onclick="window.switchModel('${provider.providerName}', '${provider.uuid}')">
                                <i class="fas fa-exchange-alt"></i> 切换
                            </button>
                        </div>
                    </div>
                `;
            });
            html += '</div>';
            contentEl.innerHTML = html;
        } catch (error) {
            contentEl.innerHTML = `
                <div class="empty-state error">
                    <i class="fas fa-exclamation-triangle"></i>
                    <p>加载失败: ${error.message}</p>
                </div>
            `;
        }
    }

    // 切换模型
    window.switchModel = async function(provider, customName) {
        const input = document.getElementById(`model-input-${customName}`);
        const newModel = input.value.trim();
        
        if (!newModel) {
            alert('请输入模型名称');
            return;
        }

        try {
            const response = await fetch('/api/model-switch/switch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ provider, customName, newModel })
            });
            const result = await response.json();
            
            if (result.success) {
                alert(`模型切换成功: ${result.data.oldModel} -> ${result.data.newModel}`);
                renderModels();
            } else {
                alert(`切换失败: ${result.error}`);
            }
        } catch (error) {
            alert(`切换失败: ${error.message}`);
        }
    };

    // 注入菜单项
    function injectMenuItem() {
        const nav = document.querySelector('.sidebar-nav');
        if (!nav) {
            console.warn(`[${PLUGIN_ID}] Sidebar nav not found`);
            return false;
        }

        // 检查是否已经注入
        if (document.getElementById(MENU_ID)) {
            return true;
        }

        const insertAfter = document.getElementById(menuConfig.insertAfter);
        const navItem = document.createElement('a');
        navItem.href = '#gpu-monitor';
        navItem.className = 'nav-item';
        navItem.id = menuConfig.id;
        navItem.dataset.section = menuConfig.section;
        navItem.innerHTML = `<i class="${menuConfig.icon}" aria-hidden="true"></i> <span>${menuConfig.label}</span>`;

        if (insertAfter) {
            insertAfter.after(navItem);
        } else {
            nav.appendChild(navItem);
        }

        console.log(`[${PLUGIN_ID}] Menu item injected`);
        return true;
    }

    // 注入 Section
    function injectSection() {
        const contentContainer = document.getElementById('content-container');
        if (!contentContainer) {
            console.warn(`[${PLUGIN_ID}] Content container not found`);
            return false;
        }

        // 检查是否已经注入
        if (document.getElementById(SECTION_ID)) {
            return true;
        }

        contentContainer.insertAdjacentHTML('beforeend', sectionHTML);
        console.log(`[${PLUGIN_ID}] Section injected`);
        return true;
    }

    // 初始化导航事件
    function initNavigation() {
        const navItem = document.getElementById(MENU_ID);
        if (!navItem) return;

        navItem.addEventListener('click', function(e) {
            e.preventDefault();

            // 更新导航状态
            document.querySelectorAll('.nav-item').forEach(item => item.classList.remove('active'));
            navItem.classList.add('active');

            // 显示对应 section
            document.querySelectorAll('.section').forEach(section => {
                section.style.display = 'none';
            });

            const targetSection = document.getElementById('gpu-monitor');
            if (targetSection) {
                targetSection.style.display = 'block';
            }

            // 加载数据
            loadGPUData();
            renderModels();
        });
    }

    // 绑定刷新按钮事件
    function bindEvents() {
        const refreshBtn = document.getElementById('gpuRefreshBtn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                loadGPUData();
                renderModels();
            });
        }
    }

    // 主初始化函数
    function init() {
        console.log(`[${PLUGIN_ID}] Initializing menu injection...`);
        
        injectStyles();
        const menuInjected = injectMenuItem();
        const sectionInjected = injectSection();

        if (menuInjected && sectionInjected) {
            initNavigation();
            bindEvents();
            console.log(`[${PLUGIN_ID}] Menu injection complete`);
        }
    }

    // 立即执行一次初始化
    function tryInit() {
        if (document.querySelector('.sidebar-nav') && document.getElementById('content-container')) {
            init();
        } else {
            setTimeout(tryInit, 500);
        }
    }

    // 等待 DOM 加载完成后开始
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', tryInit);
    } else {
        tryInit();
    }

})();
