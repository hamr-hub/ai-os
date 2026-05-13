(function() {
    const DEFAULT_LIMITS = {
        min: 60,
        hour: 120,
        day: 240,
    };

    const METRIC_PRESETS = [
        {
            key: 'utilization',
            label: 'GPU 利用率',
            icon: 'fa-microchip',
            currentId: 'aios-gpu-chart-util-current',
            canvasId: 'aios-gpu-chart-util',
            xAxisId: 'aios-gpu-chart-util-x-axis',
            yAxisId: 'aios-gpu-chart-util-y-axis',
            unit: '%',
            color: 'rgb(129, 140, 248)',
            min: 0,
            max: 100,
            titleClass: 'aios-p-util',
            valueFormatter: value => (Number.isFinite(value) ? `${value.toFixed(0)}%` : '--')
        },
        {
            key: 'memory',
            label: '显存占用',
            icon: 'fa-memory',
            currentId: 'aios-gpu-chart-mem-current',
            canvasId: 'aios-gpu-chart-mem',
            xAxisId: 'aios-gpu-chart-mem-x-axis',
            yAxisId: 'aios-gpu-chart-mem-y-axis',
            unit: '%',
            color: 'rgb(52, 211, 153)',
            min: 0,
            max: 100,
            titleClass: 'aios-p-mem',
            valueFormatter: value => (Number.isFinite(value) ? `${value.toFixed(1)}%` : '--')
        },
        {
            key: 'temperature',
            label: '温度',
            icon: 'fa-thermometer-half',
            currentId: 'aios-gpu-chart-temp-current',
            canvasId: 'aios-gpu-chart-temp',
            xAxisId: 'aios-gpu-chart-temp-x-axis',
            yAxisId: 'aios-gpu-chart-temp-y-axis',
            unit: '°C',
            color: 'rgb(251, 191, 36)',
            min: 0,
            max: null,
            titleClass: 'aios-p-temp',
            valueFormatter: value => (Number.isFinite(value) ? `${value.toFixed(0)}°C` : '--')
        },
        {
            key: 'power',
            label: '功耗',
            icon: 'fa-bolt',
            currentId: 'aios-gpu-chart-power-current',
            canvasId: 'aios-gpu-chart-power',
            xAxisId: 'aios-gpu-chart-power-x-axis',
            yAxisId: 'aios-gpu-chart-power-y-axis',
            unit: 'W',
            color: 'rgb(248, 113, 113)',
            min: 0,
            max: null,
            titleClass: 'aios-p-power',
            valueFormatter: value => (Number.isFinite(value) ? `${value.toFixed(0)}W` : '--')
        },
    ];

    function normalizeTimeRange(value) {
        const range = String(value || 'min').toLowerCase();
        if (['min', 'minute', 'minutes', '1m', 'm'].includes(range)) return 'min';
        if (['hour', 'hours', 'h', 'hr'].includes(range)) return 'hour';
        if (['day', 'days', 'd'].includes(range)) return 'day';
        return 'min';
    }

    function toNumber(value) {
        const num = Number(value);
        return Number.isFinite(num) ? num : null;
    }

    function formatBytes(bytes) {
        if (!bytes || bytes === 0) return '0 B';
        const k = 1024;
        const units = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${units[i]}`;
    }

    function pickNumber(source, keys) {
        for (const key of keys) {
            const raw = source?.[key];
            const num = toNumber(raw);
            if (num !== null) return num;
        }
        return null;
    }

    function downsamplePoints(points, maxPoints) {
        if (!Array.isArray(points) || points.length <= maxPoints) return points;
        const bucketSize = Math.max(1, points.length / maxPoints);
        const sampled = [];
        for (let bucket = 0; bucket < maxPoints; bucket += 1) {
            const start = Math.floor(bucket * bucketSize);
            const end = Math.min(points.length, Math.floor((bucket + 1) * bucketSize));
            const slice = points.slice(start, Math.max(start + 1, end));
            if (!slice.length) continue;
            const peak = slice.reduce((best, item) => {
                if (!best) return item;
                const bestScore = Math.abs((best?.utilization ?? 0)) + Math.abs((best?.memory ?? 0)) + Math.abs((best?.temperature ?? 0)) + Math.abs((best?.power ?? 0));
                const itemScore = Math.abs((item?.utilization ?? 0)) + Math.abs((item?.memory ?? 0)) + Math.abs((item?.temperature ?? 0)) + Math.abs((item?.power ?? 0));
                return itemScore >= bestScore ? item : best;
            }, null);
            sampled.push(peak || slice[slice.length - 1]);
        }
        const first = points[0];
        const last = points[points.length - 1];
        if (sampled[0] !== first) sampled.unshift(first);
        if (sampled[sampled.length - 1] !== last) sampled.push(last);
        return sampled.slice(-maxPoints);
    }

    function normalizeHistoryPayload(payload) {
        const source = payload?.history ?? payload?.data ?? payload;
        const list = Array.isArray(source) ? source : [];

        return list
            .map((item) => {
                const utilization = pickNumber(item, ['utilization', 'gpu_utilization', 'gpuUtilization', 'util']);
                const memory = pickNumber(item, ['memory_utilization', 'memoryUtilization', 'memory', 'memoryUsagePercent']);
                const temperature = pickNumber(item, ['temperature', 'temp', 'temperature_c']);
                const power = pickNumber(item, ['power_draw', 'power', 'powerUsage', 'power_watts']);
                const timestamp = item.timestamp || item.time || item.ts || null;
                return {
                    timestamp,
                    utilization,
                    memory,
                    temperature,
                    power,
                };
            })
            .filter((entry) => entry.timestamp && Number.isFinite(pickNumber(entry, ['utilization', 'memory', 'temperature', 'power'])))
            .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
    }

    function toAxisDateLabel(range, date) {
        const h = String(date.getHours()).padStart(2, '0');
        const m = String(date.getMinutes()).padStart(2, '0');
        if (range === 'day') {
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const day = String(date.getDate()).padStart(2, '0');
            return `${month}-${day}`;
        }
        const s = String(date.getSeconds()).padStart(2, '0');
        return range === 'hour' ? `${h}:${m}` : `${h}:${m}:${s}`;
    }

    function drawMiniChart(canvas, values, labels, config) {
        const canvasEl = document.getElementById(canvas);
        if (!canvasEl) return;

        const points = Array.isArray(values) ? values : [];
        const valid = points.filter(value => Number.isFinite(value));
        if (!valid.length) {
            const ctx = canvasEl.getContext('2d');
            const w = canvasEl.parentElement.clientWidth || 200;
            const h = 120;
            canvasEl.width = w;
            canvasEl.height = h;
            ctx.clearRect(0, 0, w, h);
            return;
        }

        const w = canvasEl.parentElement.clientWidth || 200;
        const h = 120;
        const padding = { left: 38, right: 10, top: 8, bottom: 24 };
        canvasEl.width = w;
        canvasEl.height = h;

        const min = config.min ?? 0;
        const candidateMax = config.max != null ? config.max : Math.max(...valid, 0);
        const max = candidateMax > min ? candidateMax : (min + 1);
        const plotHeight = h - padding.top - padding.bottom;
        const plotWidth = w - padding.left - padding.right;
        const toX = (idx) => padding.left + (plotWidth * idx) / Math.max(points.length - 1, 1);
        const toY = (value) => h - padding.bottom - ((value - min) / (max - min || 1)) * plotHeight;

        const ctx = canvasEl.getContext('2d');
        ctx.clearRect(0, 0, w, h);
        ctx.beginPath();
        ctx.strokeStyle = config.color;
        ctx.lineWidth = 1.8;

        let firstPoint = true;
        points.forEach((value, idx) => {
            const x = toX(idx);
            const y = toY(Math.min(Math.max(value, min), max));
            if (firstPoint) {
                ctx.moveTo(x, y);
                firstPoint = false;
            } else {
                ctx.lineTo(x, y);
            }
        });
        ctx.stroke();

        if (points.length > 1) {
            ctx.lineTo(toX(points.length - 1), h - padding.bottom);
            ctx.lineTo(padding.left, h - padding.bottom);
            ctx.closePath();
            ctx.fillStyle = config.fill;
            ctx.fill();
        }

        if (config.axis) {
            const axisEl = document.getElementById(config.axis.id);
            if (axisEl) {
                const xEntries = labels.length ? labels : points;
                const labelCount = 4;
                axisEl.innerHTML = '';
                for (let i = 0; i < labelCount; i++) {
                    const idx = Math.floor((xEntries.length - 1) * i / Math.max(labelCount - 1, 1));
                    const target = new Date(xEntries[idx]);
                    const d = Number.isNaN(target.getTime()) ? new Date() : target;
                    axisEl.innerHTML += `<span class="aios-p-axis-label">${toAxisDateLabel(config.range, d)}</span>`;
                }
            }

            const yAxisEl = document.getElementById(config.axis.y);
            if (yAxisEl) {
                const mid = Math.round((min + max) / 2);
                yAxisEl.innerHTML = [
                    `<span class="aios-p-y-label">${max.toFixed(0)}</span>`,
                    `<span class="aios-p-y-label">${mid.toFixed(0)}${config.unit}</span>`,
                    `<span class="aios-p-y-label">${min.toFixed(0)}${config.unit}</span>`
                ].join('');
            }
        }
    }

    function escapeHtmlValue(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function renderSummaryCard(containerId, state = {}) {
        const container = document.getElementById(containerId);
        if (!container) return;
        const {
            loading = false,
            lastUpdated = '',
            lastError = '',
            isMonitoring = true
        } = state;
        if (!isMonitoring) {
            container.innerHTML = `<div class="aios-p-summary-card aios-p-card">
                <div class="aios-p-summary-main">
                    <div class="aios-p-summary-title"><i class="fas fa-wave-square"></i> 监控状态</div>
                    <div class="aios-p-summary-meta">数据采集未启用</div>
                </div>
                <div class="aios-p-summary-side"><span class="aios-p-summary-pill">监控未启动</span></div>
            </div>`;
            return;
        }
        container.innerHTML = `<div class="aios-p-summary-card ${loading ? 'is-loading' : ''}">
            <div class="aios-p-summary-main">
                <div class="aios-p-summary-title"><i class="fas fa-wave-square"></i> 监控状态</div>
                <div class="aios-p-summary-meta">${loading ? '正在刷新 GPU / 引擎状态…' : '数据刷新正常'}</div>
            </div>
            <div class="aios-p-summary-side">
                <span class="aios-p-summary-pill ${lastError ? 'is-error' : ''}">${lastError ? `异常: ${escapeHtmlValue(lastError)}` : `最近更新 ${escapeHtmlValue(lastUpdated || '-')}`}</span>
            </div>
        </div>`;
    }

    function renderGPUCards(containerId, gpu, refreshMeta = {}) {
        const container = document.getElementById(containerId);
        if (!container) return;
        if (!gpu) {
            container.innerHTML = `<div class="aios-p-empty">未检测到 GPU</div>`;
            return;
        }
        const util = Number(gpu.gpuUtilization ?? 0);
        const memUsed = Number(gpu.memoryUsed ?? 0);
        const memTotal = Number(gpu.memoryTotal ?? 0);
        const memPct = memTotal > 0 ? (memUsed / memTotal * 100) : 0;
        const temp = Number(gpu.temperature ?? 0);
        const power = Number(gpu.powerDraw ?? 0);
        if (refreshMeta && refreshMeta.lastError) {
            container.innerHTML = `<div class="aios-p-summary-card"><div class="aios-p-summary-title">异常</div><div class="aios-p-summary-meta">历史状态: ${escapeHtmlValue(refreshMeta.lastError)}</div></div>`;
        }
        const cards = [
            { icon: 'fa-tag', label: 'GPU', value: gpu.name || '-' },
            { icon: 'fa-chart-line', label: '利用率', value: `${util}%`, progress: util, ptype: util > 80 ? 'danger' : util > 50 ? 'warning' : 'success' },
            { icon: 'fa-memory', label: '显存', value: `${formatBytes(memUsed)} / ${formatBytes(memTotal)}`, progress: memPct, ptype: memPct > 80 ? 'danger' : memPct > 50 ? 'warning' : 'success' },
            { icon: 'fa-thermometer-half', label: '温度', value: `${temp}°C`, progress: temp, ptype: temp > 80 ? 'danger' : temp > 60 ? 'warning' : 'success' },
            { icon: 'fa-plug', label: '功耗', value: `${power}W` },
        ];
        container.innerHTML = cards.map(c => {
            const prog = c.progress != null ? `<div class="aios-p-progress-bar"><div class="aios-p-progress-fill aios-${c.ptype}" style="width:${Math.min(c.progress, 100)}%"></div></div>` : '';
            return `<div class="aios-p-stat-card"><div class="aios-p-stat-icon"><i class="fas ${c.icon}"></i></div><div class="aios-p-stat-body"><div class="aios-p-stat-label">${c.label}</div><div class="aios-p-stat-value">${c.value}</div>${prog}</div></div>`;
        }).join('');
        const summaryContainer = document.getElementById('aios-gpu-summary');
        if (summaryContainer) {
            summaryContainer.innerHTML = `<div class="aios-p-summary-grid">
                <div class="aios-p-summary-card"><div class="aios-p-summary-title"><i class="fas fa-tag"></i> 设备</div><div class="aios-p-summary-value">${escapeHtmlValue(gpu.name || '-')}</div><div class="aios-p-summary-meta">驱动 ${escapeHtmlValue(String(gpu.driverVersion || gpu.driver_version || '-'))}</div></div>
                <div class="aios-p-summary-card"><div class="aios-p-summary-title"><i class="fas fa-gauge-high"></i> 负载概览</div><div class="aios-p-summary-value">${util.toFixed(1)}% / ${memPct.toFixed(1)}%</div><div class="aios-p-summary-meta">利用率 / 显存占用</div></div>
                <div class="aios-p-summary-card"><div class="aios-p-summary-title"><i class="fas fa-clock"></i> 刷新时间</div><div class="aios-p-summary-value">${escapeHtmlValue(refreshMeta.lastUpdated || '-')}</div><div class="aios-p-summary-meta">${refreshMeta.lastError ? `异常: ${escapeHtmlValue(refreshMeta.lastError)}` : '采样正常'}</div></div>
            </div>`;
        }
    }

    function renderGpuHistoryMissing(containerId, range) {
        const container = document.getElementById(containerId);
        if (!container) return;
        container.innerHTML = `<div class="aios-p-status-banner"><div class="aios-p-inline-status aios-p-inline-status-warning"><i class="fas fa-circle-info"></i><span>${formatNoDataText(range)}</span></div></div>`;
    }

    function renderMetricCards(root, range, dataset, config) {
        return `
            <div class="aios-p-chart-section">
                <div class="aios-p-chart-metrics-grid" data-range="${range}" id="${root.id}-grid">
                    ${METRIC_PRESETS.map(preset => {
                        const value = dataset[preset.key];
                const hasValue = Number.isFinite(value) && value >= 0;
                const current = hasValue ? preset.valueFormatter(value) : '--';
                return `
                            <div class="aios-p-card" data-metric="${preset.key}">
                                <div class="aios-p-chart-header">
                                    <div class="aios-p-chart-header-left">
                                        <h3 class="${preset.titleClass}"><i class="fas ${preset.icon}"></i>${preset.label}</h3>
                                    </div>
                                    <div class="aios-p-chart-current" id="${preset.currentId}">${current}</div>
                                </div>
                                <div class="aios-p-chart-wrapper">
                                    <div class="aios-p-chart-canvas-wrap">
                                        <canvas class="aios-p-canvas" id="${preset.canvasId}"></canvas>
                                        <div class="aios-p-chart-axis" id="${preset.xAxisId}"></div>
                                        <div class="aios-p-chart-y-axis" id="${preset.yAxisId}"></div>
                                    </div>
                                </div>
                            </div>
                        `;
                    }).join('')}
                </div>
            </div>`;
    }

    function formatNoDataText(range) {
        if (range === 'min') return '无最近 1 分钟数据';
        if (range === 'hour') return '无最近 1 小时数据';
        return '无最近 1 天数据';
    }

    class AiosGPUHistoryPanel {
        constructor(rootId, options = {}) {
            this.rootId = rootId;
            this.root = null;
            this.lastRange = 'min';
            this.lastDataset = [];
            this.lastSummary = null;
            this.lastRangePoints = options.limit || DEFAULT_LIMITS;
        }

        mount() {
            this.root = document.getElementById(this.rootId);
            if (!this.root) return this;
            this.root.innerHTML = `<div class="loading">加载中...</div>`;
            this.render();
            return this;
        }

        setRange(range) {
            this.lastRange = normalizeTimeRange(range);
            this.render();
            return this;
        }

        setSummary(data) {
            this.lastSummary = data || null;
            return this;
        }

        update(history, options = {}) {
            this.lastDataset = normalizeHistoryPayload(history);
            if (options.range) this.lastRange = normalizeTimeRange(options.range);
            if (options.limit) this.lastRangePoints = options.limit;
            if (Object.prototype.hasOwnProperty.call(options, 'summary')) {
                this.lastSummary = options.summary || null;
            }
            this.render();
            return this;
        }

        getRangeLimit() {
            return this.lastRangePoints[this.lastRange] || this.lastRangePoints.min;
        }

        getSeriesFor(metric) {
            const keyMap = { utilization: 'utilization', memory: 'memory', temperature: 'temperature', power: 'power' };
            const key = keyMap[metric];
            return this.lastDataset
                .map(item => item[key])
                .filter(value => Number.isFinite(value))
                .map(value => Number(value));
        }

        getLatestValue(metric) {
            const series = this.getSeriesFor(metric);
            return series.length ? series[series.length - 1] : null;
        }

        getLatestTimestamp() {
            if (!this.lastDataset.length) return null;
            return this.lastDataset[this.lastDataset.length - 1].timestamp || null;
        }

        getAxisTimestamps() {
            return this.lastDataset.map(item => item.timestamp);
        }

        render() {
            if (!this.root) return;
            const normalizedRange = this.lastRange;
            const rawCount = this.getRangeLimit();
            const sliced = downsamplePoints(this.lastDataset, rawCount);

            if (!sliced.length) {
                this.root.innerHTML = `
                    <div class="aios-p-status-banner">
                        <div class="aios-p-inline-status aios-p-inline-status-warning">
                            <i class="fas fa-circle-info"></i><span>${formatNoDataText(normalizedRange)}</span>
                        </div>
                    </div>`;
                return;
            }
            this.lastDataset = sliced;
            const currentValues = {
                utilization: this.getLatestValue('utilization'),
                memory: this.getLatestValue('memory'),
                temperature: this.getLatestValue('temperature'),
                power: this.getLatestValue('power'),
            };
            this.root.innerHTML = renderMetricCards(this.root, normalizedRange, currentValues, METRIC_PRESETS);

            const timestamps = this.getAxisTimestamps();
            const drawEnv = {
                range: normalizedRange,
                unit: '',
                axis: { id: null, y: null },
            };
            const maxByMetric = {
                utilization: 100,
                memory: 100,
                temperature: null,
                power: null,
            };
            for (const preset of METRIC_PRESETS) {
                const series = this.getSeriesFor(preset.key);
                const min = preset.min != null ? preset.min : 0;
                const maxDefault = maxByMetric[preset.key] != null ? maxByMetric[preset.key] : Math.max(...series, 1);
                drawMiniChart(preset.canvasId, series, timestamps, {
                    color: preset.color,
                    fill: preset.color.replace(')', ', 0.14)').replace('rgb', 'rgba'),
                    min,
                    max: preset.max != null ? preset.max : maxDefault,
                    unit: preset.unit,
                    axis: {
                        id: preset.xAxisId,
                        y: preset.yAxisId,
                    },
                    range: normalizedRange,
                });
            }
        }
    }

    window.AiosGPUCharts = {
        renderSummaryCard,
        renderGPUCards,
        renderGpuHistoryMissing,
        createDashboard(containerId, options = {}) {
            const panel = new AiosGPUHistoryPanel(containerId, options);
            return panel.mount();
        },
        normalizeHistoryPayload,
    };
})();
