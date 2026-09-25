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
    const profileTrigger = profileMenu?.querySelector('summary');
    const sidebar = document.querySelector('#supervisor-sidebar');
    const sidebarOpenButtons = Array.from(
        document.querySelectorAll('[data-sidebar-open]')
    );
    const sidebarCloseButtons = Array.from(
        document.querySelectorAll('[data-sidebar-close]')
    );
    const sidebarMedia = window.matchMedia('(max-width: 880px)');
    let lastSidebarTrigger = null;

    const applyTheme = (theme, persist = false) => {
        const selectedTheme = theme === 'dark' ? 'dark' : 'light';

        root.dataset.supervisorTheme = selectedTheme;
        root.style.colorScheme = selectedTheme;

        if (persist) {
            try {
                localStorage.setItem(storageKey, selectedTheme);
            } catch (_) {
                // O painel continua funcionando quando o navegador bloqueia storage.
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

    const setSidebarExpanded = (expanded) => {
        sidebarOpenButtons.forEach((button) => {
            button.setAttribute('aria-expanded', String(expanded));
        });
    };

    const setSidebarAvailability = (available) => {
        if (!sidebar) {
            return;
        }

        sidebar.inert = !available;

        if (available) {
            sidebar.removeAttribute('aria-hidden');
        } else {
            sidebar.setAttribute('aria-hidden', 'true');
        }
    };

    const syncSidebar = () => {
        if (!sidebar) {
            return;
        }

        if (!sidebarMedia.matches) {
            body.classList.remove('is-sidebar-open');
            setSidebarAvailability(true);
            setSidebarExpanded(false);
            return;
        }

        const isOpen = body.classList.contains('is-sidebar-open');
        setSidebarAvailability(isOpen);
        setSidebarExpanded(isOpen);
    };

    const openSidebar = (trigger) => {
        if (!sidebar || !sidebarMedia.matches) {
            return;
        }

        lastSidebarTrigger = trigger || sidebarOpenButtons[0] || null;
        setSidebarAvailability(true);
        body.classList.add('is-sidebar-open');
        setSidebarExpanded(true);

        window.requestAnimationFrame(() => {
            sidebar.querySelector('[data-sidebar-close]')?.focus();
        });
    };

    const closeSidebar = (restoreFocus = true) => {
        const wasOpen = body.classList.contains('is-sidebar-open');

        if (restoreFocus && wasOpen) {
            const focusTarget = lastSidebarTrigger || sidebarOpenButtons[0];
            focusTarget?.focus();
        }

        body.classList.remove('is-sidebar-open');
        syncSidebar();
    };

    const getFocusableElements = (container) => {
        if (!container) {
            return [];
        }

        return Array.from(container.querySelectorAll(
            'a[href], button:not([disabled]), input:not([disabled]), '
            + 'select:not([disabled]), textarea:not([disabled]), '
            + '[tabindex]:not([tabindex="-1"])'
        )).filter((element) => (
            !element.hidden
            && element.getAttribute('aria-hidden') !== 'true'
            && element.getClientRects().length > 0
        ));
    };

    const profileName = profileTrigger
        ?.getAttribute('aria-label')
        ?.replace(/^Abrir menu do perfil de\s*/i, '') || 'usuario';

    const syncProfile = () => {
        if (!profileTrigger || !profileMenu) {
            return;
        }

        const isOpen = profileMenu.open;
        profileTrigger.setAttribute('aria-expanded', String(isOpen));
        profileTrigger.setAttribute(
            'aria-label',
            `${isOpen ? 'Fechar' : 'Abrir'} menu do perfil de ${profileName}`
        );
    };

    const closeProfile = (restoreFocus = false) => {
        if (!profileMenu?.open) {
            return;
        }

        profileMenu.removeAttribute('open');

        if (restoreFocus) {
            profileTrigger?.focus();
        }
    };

    const dismissMessage = (message) => {
        if (!message || message.classList.contains('is-leaving')) {
            return;
        }

        message.classList.add('is-leaving');
        window.setTimeout(() => {
            const container = message.parentElement;
            message.remove();

            if (container && !container.children.length) {
                container.remove();
            }
        }, 220);
    };

    const prepareMessages = () => {
        document.querySelectorAll('[data-supervisor-message]').forEach((message) => {
            const closeButton = message.querySelector('[data-message-close]');
            const isError = message.classList.contains('supervisor-mensagem--error');
            const delay = isError ? 9000 : 6000;
            let timerId = null;

            const stopTimer = () => {
                if (timerId !== null) {
                    window.clearTimeout(timerId);
                    timerId = null;
                }
            };

            const startTimer = () => {
                stopTimer();
                timerId = window.setTimeout(() => dismissMessage(message), delay);
            };

            closeButton?.addEventListener('click', () => {
                stopTimer();
                dismissMessage(message);
            });
            message.addEventListener('mouseenter', stopTimer);
            message.addEventListener('mouseleave', startTimer);
            message.addEventListener('focusin', stopTimer);
            message.addEventListener('focusout', (event) => {
                if (!message.contains(event.relatedTarget)) {
                    startTimer();
                }
            });

            startTimer();
        });
    };

    const enhanceTables = () => {
        document.querySelectorAll('.supervisor-tabela-wrapper').forEach((wrapper) => {
            if (!wrapper.hasAttribute('tabindex')) {
                wrapper.tabIndex = 0;
            }

            if (!wrapper.hasAttribute('role')) {
                wrapper.setAttribute('role', 'region');
            }

            if (!wrapper.hasAttribute('aria-label')) {
                const card = wrapper.closest('.supervisor-card');
                const heading = card?.querySelector('h1, h2, h3')?.textContent.trim();
                wrapper.setAttribute(
                    'aria-label',
                    heading ? `Tabela: ${heading}` : 'Tabela de registros'
                );
            }
        });
    };

    const enhanceFilterNames = () => {
        document.querySelectorAll('.supervisor-busca input').forEach((input) => {
            const hasLabel = input.getAttribute('aria-label')
                || input.getAttribute('aria-labelledby')
                || (input.id && document.querySelector(`label[for="${input.id}"]`));

            if (!hasLabel) {
                input.setAttribute('aria-label', 'Pesquisar registros');
            }
        });

        document.querySelectorAll('.supervisor-select select').forEach((select) => {
            const hasLabel = select.getAttribute('aria-label')
                || select.getAttribute('aria-labelledby')
                || (select.id && document.querySelector(`label[for="${select.id}"]`));

            if (!hasLabel) {
                select.setAttribute('aria-label', 'Filtrar registros');
            }
        });
    };

    applyTheme(root.dataset.supervisorTheme);
    syncSidebar();
    syncProfile();
    prepareMessages();
    enhanceTables();
    enhanceFilterNames();

    themeButton?.addEventListener('click', () => {
        const nextTheme = root.dataset.supervisorTheme === 'dark'
            ? 'light'
            : 'dark';

        applyTheme(nextTheme, true);
    });

    sidebarOpenButtons.forEach((button) => {
        button.addEventListener('click', () => openSidebar(button));
    });

    sidebarCloseButtons.forEach((button) => {
        button.addEventListener('click', () => closeSidebar(true));
    });

    profileMenu?.addEventListener('toggle', syncProfile);

    document.addEventListener('click', (event) => {
        if (profileMenu?.open && !profileMenu.contains(event.target)) {
            closeProfile(false);
        }

        const confirmButton = event.target.closest?.('[data-confirm]');

        if (confirmButton) {
            const form = confirmButton.form;

            if (form && !form.checkValidity()) {
                event.preventDefault();
                form.reportValidity();
                return;
            }

            if (!window.confirm(confirmButton.dataset.confirm)) {
                event.preventDefault();
            }
        }
    });

    document.addEventListener('keydown', (event) => {
        if (
            event.key === 'Tab'
            && sidebarMedia.matches
            && body.classList.contains('is-sidebar-open')
        ) {
            const focusable = getFocusableElements(sidebar);
            const firstElement = focusable[0];
            const lastElement = focusable[focusable.length - 1];

            if (!firstElement || !lastElement) {
                event.preventDefault();
                return;
            }

            if (event.shiftKey && document.activeElement === firstElement) {
                event.preventDefault();
                lastElement.focus();
            } else if (
                !event.shiftKey
                && document.activeElement === lastElement
            ) {
                event.preventDefault();
                firstElement.focus();
            } else if (!sidebar.contains(document.activeElement)) {
                event.preventDefault();
                firstElement.focus();
            }
        }

        if (event.key !== 'Escape') {
            return;
        }

        if (profileMenu?.open) {
            closeProfile(true);
        }

        if (body.classList.contains('is-sidebar-open')) {
            closeSidebar(true);
        }
    });

    if (typeof sidebarMedia.addEventListener === 'function') {
        sidebarMedia.addEventListener('change', syncSidebar);
    } else {
        sidebarMedia.addListener(syncSidebar);
    }

    window.addEventListener('storage', (event) => {
        if (
            event.key === storageKey
            && (event.newValue === 'light' || event.newValue === 'dark')
        ) {
            applyTheme(event.newValue);
        }
    });
})();
