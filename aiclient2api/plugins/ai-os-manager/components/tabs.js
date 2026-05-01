(function(window) {
    'use strict';

    function init(containerSelector, onChange) {
        var container = document.querySelector(containerSelector);
        if (!container) return;

        var tabs = container.querySelectorAll('.gpum-tab');
        var panels = container.querySelectorAll('.gpum-tab-panel');

        tabs.forEach(function(tab) {
            tab.addEventListener('click', function() {
                var targetId = tab.dataset.tab;
                tabs.forEach(function(t) { t.classList.remove('gpum-active'); });
                tab.classList.add('gpum-active');
                panels.forEach(function(p) { p.classList.remove('gpum-active'); });
                var target = document.getElementById(targetId);
                if (target) target.classList.add('gpum-active');
                if (onChange) onChange(targetId);
            });
        });
    }

    window.AiosTabs = { init: init };
})(window);
