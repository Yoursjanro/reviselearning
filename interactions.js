/* Global neon interaction layer — works offline, no external libraries. */
(() => {
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  document.documentElement.classList.add('motion-ready');

  // Scroll reveal for major content blocks across admin, student and login pages.
  const revealSelectors = '.container > *, .container .card, .container .course-card, .container .stat, .container .achievement, .arc .game-card, .arc .game-tile, .gs > *, .login-card';
  const candidates = [...document.querySelectorAll(revealSelectors)];
  candidates.forEach((el, i) => {
    if (el.closest('.game-panel, .question-stage') && el.querySelector('.game-option')) return;
    el.classList.add('scroll-reveal');
    el.style.setProperty('--reveal-delay', `${Math.min(i % 5, 4) * 55}ms`);
  });
  if ('IntersectionObserver' in window && !reduceMotion) {
    const observer = new IntersectionObserver(entries => entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        observer.unobserve(entry.target);
      }
    }), { threshold: 0.08, rootMargin: '0px 0px -35px 0px' });
    document.querySelectorAll('.scroll-reveal').forEach(el => observer.observe(el));
  } else document.querySelectorAll('.scroll-reveal').forEach(el => el.classList.add('is-visible'));

  // Global click ripple and press feedback for buttons, links and interactive cards.
  document.addEventListener('click', event => {
    const target = event.target.closest('button, .btn, .nav a, .list-link, .course-card, .stat, .achievement, .game-option, .game-btn, [role="button"]');
    if (!target || target.matches(':disabled') || reduceMotion) return;
    const rect = target.getBoundingClientRect();
    const ripple = document.createElement('span');
    ripple.className = 'click-ripple';
    ripple.style.left = `${event.clientX - rect.left}px`;
    ripple.style.top = `${event.clientY - rect.top}px`;
    target.appendChild(ripple);
    target.classList.remove('tap-pop');
    void target.offsetWidth;
    target.classList.add('tap-pop');
    window.setTimeout(() => { ripple.remove(); target.classList.remove('tap-pop'); }, 650);
  }, { passive: true });

  // Scroll progress indicator.
  const progress = document.createElement('div');
  progress.className = 'scroll-progress';
  progress.setAttribute('aria-hidden', 'true');
  document.body.appendChild(progress);
  let scheduled = false;
  const updateScroll = () => {
    const max = document.documentElement.scrollHeight - window.innerHeight;
    progress.style.transform = `scaleX(${max > 0 ? window.scrollY / max : 0})`;
    document.body.classList.toggle('has-scrolled', window.scrollY > 16);
    scheduled = false;
  };
  window.addEventListener('scroll', () => {
    if (!scheduled) { scheduled = true; requestAnimationFrame(updateScroll); }
  }, { passive: true });
  updateScroll();

  // Soft pointer-follow glow on desktop only.
  if (window.matchMedia('(pointer:fine)').matches && !reduceMotion) {
    const glow = document.createElement('div');
    glow.className = 'pointer-glow';
    glow.setAttribute('aria-hidden', 'true');
    document.body.appendChild(glow);
    let raf = 0, x = -300, y = -300;
    document.addEventListener('pointermove', e => {
      x = e.clientX; y = e.clientY;
      if (!raf) raf = requestAnimationFrame(() => {
        glow.style.transform = `translate3d(${x - 180}px, ${y - 180}px, 0)`;
        raf = 0;
      });
    }, { passive: true });
  }
})();
