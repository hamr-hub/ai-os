(function(window) {
    'use strict';

    function esc(str) {
        var div = document.createElement('div');
        div.textContent = String(str || '');
        return div.innerHTML;
    }

    function show(msg, type) {
        var container = document.querySelector('.aios-toast-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'aios-toast-container';
            document.body.appendChild(container);
        }

        var toast = document.createElement('div');
        toast.className = 'aios-toast aios-toast-' + (type || 'info');
        toast.innerHTML = '<span>' + esc(msg) + '</span><button class="aios-toast-close" onclick="this.parentElement.remove()">&times;</button>';
        container.appendChild(toast);
        setTimeout(function() {
            if (toast.parentElement) {
                toast.style.opacity = '0';
                toast.style.transform = 'translateX(100%)';
                toast.style.transition = 'all 0.3s ease';
                setTimeout(function() { if (toast.parentElement) toast.remove(); }, 300);
            }
        }, 4000);
    }

    window.AiosToast = { show: show };
})(window);
