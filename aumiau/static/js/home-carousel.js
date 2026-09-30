document.addEventListener('DOMContentLoaded', () => {
    const carousel = document.querySelector('[data-home-carousel]');
    const track = carousel?.querySelector('[data-carousel-track]');
    const previous = carousel?.querySelector('[data-carousel-prev]');
    const next = carousel?.querySelector('[data-carousel-next]');
    const status = carousel?.querySelector('[data-carousel-status]');
    const cards = track ? Array.from(track.querySelectorAll('.pet-card')) : [];
    if (!track || !previous || !next || !cards.length) return;

    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const cardStep = () => {
        const gap = parseFloat(getComputedStyle(track).columnGap) || 0;
        return cards[0].getBoundingClientRect().width + gap;
    };

    const update = () => {
        const maxScroll = Math.max(0, track.scrollWidth - track.clientWidth);
        previous.disabled = track.scrollLeft <= 2;
        next.disabled = track.scrollLeft >= maxScroll - 2;

        if (!status) return;
        const visible = cards.map((card, index) => ({ card, index })).filter(({ card }) => {
            const bounds = card.getBoundingClientRect();
            const viewport = track.getBoundingClientRect();
            return bounds.right > viewport.left + 8 && bounds.left < viewport.right - 8;
        });
        if (visible.length) {
            status.textContent = `${visible[0].index + 1}–${visible.at(-1).index + 1} de ${cards.length} pets`;
        }
    };

    const move = (direction) => track.scrollBy({
        left: direction * cardStep(),
        behavior: reducedMotion.matches ? 'auto' : 'smooth',
    });

    previous.addEventListener('click', () => move(-1));
    next.addEventListener('click', () => move(1));
    track.addEventListener('keydown', (event) => {
        if (event.target !== track || !['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
        event.preventDefault();
        move(event.key === 'ArrowRight' ? 1 : -1);
    });

    let statusTimer;
    track.addEventListener('scroll', () => {
        previous.disabled = track.scrollLeft <= 2;
        next.disabled = track.scrollLeft >= track.scrollWidth - track.clientWidth - 2;
        clearTimeout(statusTimer);
        statusTimer = setTimeout(update, 140);
    }, { passive: true });
    window.addEventListener('resize', update);
    update();
});
