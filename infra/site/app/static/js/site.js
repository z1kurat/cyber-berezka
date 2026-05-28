document.addEventListener('DOMContentLoaded', () => {
  // === Stagger-load node-cards (opacity fade-in only, leaves transform free for tilt) ===
  const nodeCards = document.querySelectorAll('.node-card');
  nodeCards.forEach((card, i) => {
    setTimeout(() => card.classList.add('loaded'), 1600 + i * 200);
  });

  // === Scroll progress + nav + parallax preview ===
  const progress = document.getElementById('scrollProgress');
  const nav = document.getElementById('nav');
  const previewStage = document.getElementById('previewStage');
  function onScroll() {
    const max = document.documentElement.scrollHeight - window.innerHeight;
    const pct = Math.min(100, (window.scrollY / max) * 100);
    progress.style.width = pct + '%';
    nav.classList.toggle('scrolled', window.scrollY > 30);
    if (previewStage) {
      const rect = previewStage.getBoundingClientRect();
      const center = rect.top + rect.height / 2;
      const offset = (window.innerHeight / 2 - center) * 0.08;
      previewStage.querySelectorAll('[data-speed]').forEach(card => {
        const speed = parseFloat(card.dataset.speed);
        // store parallax in CSS variable so tilt JS doesn't overwrite it
        card.style.setProperty('--parallax-y', (offset * speed) + 'px');
      });
    }
  }
  window.addEventListener('scroll', onScroll, { passive: true });

  // === Reveal observer ===
  const io = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('in');
        const section = entry.target.closest('.section, .stats-section, .about-name, .compare-section');
        if (section) section.classList.add('in-view');
      }
    });
  }, { threshold: 0.12, rootMargin: '0px 0px -80px 0px' });
  document.querySelectorAll('.reveal').forEach(el => io.observe(el));
  document.querySelectorAll('.section, .stats-section, .about-name, .compare-section').forEach(s => io.observe(s));

  function animateText(el, target) {
    const start = performance.now();
    const dur = 1200;
    function step(now) {
      const t = Math.min((now - start) / dur, 1);
      const eased = 1 - Math.pow(1 - t, 3);
      el.textContent = Math.floor(eased * target) + ' стран' + (target === 1 ? 'а' : '');
      if (t < 1) requestAnimationFrame(step);
      else el.textContent = target + ' страны';
    }
    requestAnimationFrame(step);
  }
  document.querySelectorAll('[data-count]').forEach(el => { setTimeout(() => animateText(el, parseInt(el.dataset.count)), 1500); });

  const statsIo = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.querySelectorAll('[data-counter]').forEach(el => {
          const target = parseFloat(el.dataset.counter);
          const numEl = el.querySelector('span:first-child');
          const start = performance.now();
          const dur = 1500;
          function step(now) {
            const t = Math.min((now - start) / dur, 1);
            const eased = 1 - Math.pow(1 - t, 3);
            const val = eased * target;
            numEl.textContent = target % 1 !== 0 ? val.toFixed(1) : Math.floor(val);
            if (t < 1) requestAnimationFrame(step);
            else numEl.textContent = target;
          }
          requestAnimationFrame(step);
        });
        statsIo.unobserve(entry.target);
      }
    });
  }, { threshold: 0.4 });
  const statsSection = document.querySelector('.stats-section');
  if (statsSection) statsIo.observe(statsSection);

  // === Magnetic CTA ===
  const magnet = document.getElementById('ctaMagnet');
  if (magnet) {
    magnet.addEventListener('mousemove', (e) => {
      const rect = magnet.getBoundingClientRect();
      const x = e.clientX - rect.left - rect.width / 2;
      const y = e.clientY - rect.top - rect.height / 2;
      magnet.style.transform = `translate(${x * 0.18}px, ${y * 0.25}px)`;
    });
    magnet.addEventListener('mouseleave', () => { magnet.style.transform = ''; });
  }

  // === Subtle tilt on cards (mouse-follow with perspective) ===
  document.querySelectorAll('.tilt').forEach(card => {
    let raf = null;
    // node-cards in hero preview get stronger tilt to feel more alive
    const isNode = card.classList.contains('node-card');
    const maxRot = isNode ? 6 : 3.5;
    const maxLift = isNode ? 6 : 3;
    function applyTilt(e) {
      const rect = card.getBoundingClientRect();
      const x = (e.clientX - rect.left - rect.width / 2) / (rect.width / 2);
      const y = (e.clientY - rect.top - rect.height / 2) / (rect.height / 2);
      const rotY = x * maxRot;
      const rotX = -y * maxRot;
      const tY = -maxLift + (-y * 2);
      const parallaxY = card.style.getPropertyValue('--parallax-y') || '0px';
      card.style.transform = `translateY(calc(${parallaxY} + ${tY}px)) perspective(1200px) rotateY(${rotY}deg) rotateX(${rotX}deg)`;
    }
    card.addEventListener('mousemove', (e) => {
      if (raf) cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => applyTilt(e));
    });
    card.addEventListener('mouseleave', () => {
      const parallaxY = card.style.getPropertyValue('--parallax-y') || '0px';
      card.style.transform = `translateY(${parallaxY})`;
    });
  });

  // === FAQ accordion ===
  document.querySelectorAll('.faq-q').forEach(q => {
    q.addEventListener('click', () => {
      const item = q.closest('.faq-item');
      const opened = document.querySelector('.faq-item.open');
      if (opened && opened !== item) opened.classList.remove('open');
      item.classList.toggle('open');
    });
  });
});
