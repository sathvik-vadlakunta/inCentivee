/* PracticeRank enhancement layer — progressive, dependency-free.
   Adds scroll-reveal animations, a scrolled-header shadow, and lazy-loaded
   images across the cloned site. Safe: no-ops under reduced-motion / no IO. */
(function () {
  'use strict';
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function ready(fn) {
    if (document.readyState !== 'loading') fn();
    else document.addEventListener('DOMContentLoaded', fn);
  }

  ready(function () {
    // 1) Lazy-load images that aren't already eager (perf best-practice).
    document.querySelectorAll('img:not([loading])').forEach(function (img, i) {
      if (i > 1) img.setAttribute('loading', 'lazy');     // keep first couple eager (LCP)
      img.setAttribute('decoding', 'async');
    });

    // 2) Scrolled-header shadow.
    var header = document.querySelector('header, .elementor-location-header, .site-header');
    if (header) {
      var onScroll = function () { header.classList.toggle('scrolled', window.scrollY > 12); };
      window.addEventListener('scroll', onScroll, { passive: true });
      onScroll();
    }

    if (reduce || !('IntersectionObserver' in window)) return;

    // 3) Scroll-reveal: target meaningful blocks without touching markup per page.
    var sel = [
      '.elementor-widget-heading', '.elementor-widget-text-editor',
      '.elementor-widget-image', '.elementor-widget-image-box',
      '.elementor-widget-icon-box', '.elementor-widget-button',
      '.elementor-widget-testimonial', '.entry-content > *', '.wp-block-image'
    ].join(',');

    var els = Array.prototype.slice.call(document.querySelectorAll(sel))
      .filter(function (el) {
        // skip header/nav/footer + anything already above the fold-ish
        if (el.closest('header, footer, nav, .elementor-location-header, .elementor-location-footer')) return false;
        var r = el.getBoundingClientRect();
        return r.top > 80 && r.height < window.innerHeight * 1.4;
      });

    els.forEach(function (el, i) {
      el.classList.add('pr-reveal');
      var mod = i % 3;
      if (mod) el.classList.add('pr-reveal-d' + mod);
    });

    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add('pr-in'); io.unobserve(e.target); }
      });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });

    els.forEach(function (el) { io.observe(el); });
  });
})();
