(function(window) {
    'use strict';

    function drawLineChart(canvasId, datasets, options) {
        var canvas = document.getElementById(canvasId);
        if (!canvas) return;

        var ctx = canvas.getContext('2d');
        var dpr = window.devicePixelRatio || 1;
        var width = canvas.clientWidth || 320;
        var height = canvas.clientHeight || 150;
        canvas.width = width * dpr;
        canvas.height = height * dpr;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

        ctx.clearRect(0, 0, width, height);

        var padding = (options && options.padding) || { top: 30, right: 15, bottom: 20, left: 40 };
        var chartW = width - padding.left - padding.right;
        var chartH = height - padding.top - padding.bottom;

        var allValues = [];
        datasets.forEach(function(ds) { allValues = allValues.concat(ds.data); });
        var maxVal = Math.max.apply(null, allValues.length ? allValues : [100]);
        var minVal = Math.min.apply(null, allValues.length ? allValues : [0]);
        if (maxVal === minVal) maxVal = minVal + 100;

        ctx.strokeStyle = 'rgba(148, 163, 184, 0.16)';
        ctx.lineWidth = 1;
        for (var i = 0; i <= 4; i++) {
            var y = padding.top + (chartH / 4) * i;
            ctx.beginPath();
            ctx.moveTo(padding.left, y);
            ctx.lineTo(width - padding.right, y);
            ctx.stroke();
        }

        var colors = ['#22c55e', '#3b82f6', '#f59e0b', '#ef4444', '#06b6d4', '#8b5cf6'];
        datasets.forEach(function(ds, di) {
            var color = ds.color || colors[di % colors.length];
            if (!ds.data || ds.data.length === 0) return;

            ctx.strokeStyle = color;
            ctx.lineWidth = 2;
            ctx.lineJoin = 'round';
            ctx.lineCap = 'round';
            ctx.beginPath();
            ds.data.forEach(function(val, j) {
                var x = padding.left + (ds.data.length === 1 ? chartW / 2 : (chartW / (ds.data.length - 1)) * j);
                var y = padding.top + chartH - ((val - minVal) / (maxVal - minVal)) * chartH;
                if (j === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            });
            ctx.stroke();

            var lastVal = ds.data[ds.data.length - 1];
            var lastX = padding.left + (ds.data.length === 1 ? chartW / 2 : chartW);
            var lastY = padding.top + chartH - ((lastVal - minVal) / (maxVal - minVal)) * chartH;
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(lastX, lastY, 3, 0, Math.PI * 2);
            ctx.fill();

            ctx.fillStyle = color;
            ctx.font = '11px -apple-system, BlinkMacSystemFont, sans-serif';
            ctx.textAlign = 'left';
            ctx.fillText(ds.label || ('系列' + (di + 1)), padding.left, padding.top - 10 - di * 15);
        });
    }

    function drawMiniChart(canvasId, values, color, maxValue) {
        var canvas = document.getElementById(canvasId);
        if (!canvas) return;

        var ctx = canvas.getContext('2d');
        var dpr = window.devicePixelRatio || 1;
        var width = canvas.clientWidth || 320;
        var height = canvas.clientHeight || 120;
        canvas.width = width * dpr;
        canvas.height = height * dpr;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, width, height);

        if (!values || !values.length) {
            ctx.fillStyle = 'rgba(148, 163, 184, 0.6)';
            ctx.font = '12px sans-serif';
            ctx.fillText('暂无数据', 12, height / 2);
            return;
        }

        var safeMax = Math.max(maxValue || 100, ...values, 1);
        var p = { top: 10, right: 8, bottom: 18, left: 8 };
        var cw = width - p.left - p.right;
        var ch = height - p.top - p.bottom;

        ctx.strokeStyle = 'rgba(148, 163, 184, 0.16)';
        ctx.lineWidth = 1;
        for (var i = 0; i <= 2; i++) {
            var gy = p.top + (ch / 2) * i;
            ctx.beginPath();
            ctx.moveTo(p.left, gy);
            ctx.lineTo(width - p.right, gy);
            ctx.stroke();
        }

        ctx.beginPath();
        values.forEach(function(val, idx) {
            var x = p.left + (values.length === 1 ? cw / 2 : (cw / (values.length - 1)) * idx);
            var y = p.top + ch - (Math.min(val, safeMax) / safeMax) * ch;
            if (idx === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        });
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.lineJoin = 'round';
        ctx.lineCap = 'round';
        ctx.stroke();

        var lv = values[values.length - 1];
        var lx = p.left + (values.length === 1 ? cw / 2 : cw);
        var ly = p.top + ch - (Math.min(lv, safeMax) / safeMax) * ch;
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(lx, ly, 3, 0, Math.PI * 2);
        ctx.fill();
    }

    window.AiosChart = { drawLineChart: drawLineChart, drawMiniChart: drawMiniChart };
})(window);
