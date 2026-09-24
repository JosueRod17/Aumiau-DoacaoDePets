(() => {
    'use strict';

    const root = document.documentElement;
    const body = document.body;
    const storageKey = 'aumiau-supervisor-theme';

    const themeButton = document.querySelector(
        '[data-supervisor-theme-toggle]'
    );

    const profileMenu = document.querySelector(
        '[data-supervisor-profile]'
    );

    const applyTheme = (theme, persist = false) => {
        const selectedTheme = theme === 'dark' ? 'dark' : 'light';

        root.dataset.supervisorTheme = selectedTheme;
        root.style.colorScheme = selectedTheme;

        if (persist) {
            try {
                localStorage.setItem(storageKey, selectedTheme);
            } catch (_) {
            }
        }

        if (themeButton) {
            const isDark = selectedTheme === 'dark';
            const label = isDark
                ? 'Ativar tema claro'
                : 'Ativar tema escuro';

            themeButton.setAttribute('aria-label', label);
            themeButton.title = label;
            themeButton.setAttribute('aria-pressed', String(isDark));
        }
    };

    applyTheme(root.dataset.supervisorTheme);

    themeButton?.addEventListener('click', () => {
        const nextTheme =
            root.dataset.supervisorTheme === 'dark'
                ? 'light'
                : 'dark';

        applyTheme(nextTheme, true);
    });

    document.querySelectorAll('[data-sidebar-open]').forEach((button) => {
        button.addEventListener('click', () => {
            body.classList.add('is-sidebar-open');
        });
    });

    document.querySelectorAll('[data-sidebar-close]').forEach((button) => {
        button.addEventListener('click', () => {
            body.classList.remove('is-sidebar-open');
        });
    });

    document.addEventListener('click', (event) => {
        if (
            profileMenu?.open
            && !profileMenu.contains(event.target)
        ) {
            profileMenu.removeAttribute('open');
        }

        const confirmButton = event.target.closest('[data-confirm]');

        if (
            confirmButton
            && !window.confirm(confirmButton.dataset.confirm)
        ) {
            event.preventDefault();
        }
    });

    document.addEventListener('keydown', (event) => {
        if (event.key !== 'Escape') {
            return;
        }

        profileMenu?.removeAttribute('open');
        body.classList.remove('is-sidebar-open');
    });

    window.addEventListener('storage', (event) => {
        if (
            event.key === storageKey
            && (event.newValue === 'light' || event.newValue === 'dark')
        ) {
            applyTheme(event.newValue);
        }
    });
})();
