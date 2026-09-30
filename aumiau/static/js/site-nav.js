document.addEventListener('DOMContentLoaded', () => {
    const button = document.querySelector('[data-mobile-nav-toggle]');
    const navigation = document.getElementById('site-navigation');
    if (!button || !navigation) return;

    const label = button.querySelector('[data-mobile-nav-label]');
    const setOpen = (open) => {
        document.body.classList.toggle('mobile-nav-open', open);
        button.setAttribute('aria-expanded', String(open));
        button.setAttribute('aria-label', open ? 'Fechar menu' : 'Abrir menu');
        if (label) label.textContent = open ? 'Fechar' : 'Menu';
    };

    button.addEventListener('click', () => {
        setOpen(button.getAttribute('aria-expanded') !== 'true');
    });
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && button.getAttribute('aria-expanded') === 'true') {
            setOpen(false);
            button.focus();
        }
    });
    document.addEventListener('click', (event) => {
        if (button.getAttribute('aria-expanded') === 'true' && !event.target.closest('.site-header')) {
            setOpen(false);
        }
    });
    window.matchMedia('(min-width: 701px)').addEventListener('change', (event) => {
        if (event.matches) setOpen(false);
    });
    document.body.classList.add('mobile-nav-ready');
});
