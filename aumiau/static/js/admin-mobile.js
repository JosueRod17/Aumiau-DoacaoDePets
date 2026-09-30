(() => {
    'use strict';

    const main = document.getElementById('main');
    const nav = document.getElementById('nav-sidebar');
    const toggle = document.getElementById('toggle-nav-sidebar');
    const mobile = window.matchMedia('(max-width: 900px)');

    if (!main || !nav || !toggle) return;

    // Django opens the sidebar by default. On a phone, start with the page visible.
    if (mobile.matches && main.classList.contains('shifted')) toggle.click();

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && mobile.matches && main.classList.contains('shifted')) {
            toggle.click();
            toggle.focus();
        }
    });

    document.addEventListener('click', (event) => {
        if (!mobile.matches || !main.classList.contains('shifted')) return;
        if (nav.contains(event.target) || toggle.contains(event.target)) return;
        toggle.click();
    });
})();
