/* PracticeRank enhancement layer v2 — restores interactivity lost in static
   export + modern polish. Dependency-free, defensive (each feature isolated). */
(function () {
  'use strict';
  var reduce = matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  function ready(fn){ document.readyState!=='loading'?fn():document.addEventListener('DOMContentLoaded',fn); }
  function safe(fn){ try{ fn(); }catch(e){ /* never let one feature break the rest */ } }

  ready(function () {
    // 1) perf: lazy + async images; hide broken / tiny icon-label images
    safe(function(){
      document.querySelectorAll('img:not([loading])').forEach(function(img,i){
        if(i>1) img.setAttribute('loading','lazy'); img.setAttribute('decoding','async');
      });
      document.querySelectorAll('img').forEach(function(img){
        // the original's bio "Phone"/"Email" icon imgs 404 -> hide instead of showing alt
        if(/^(phone|email|fax|icon)$/i.test(img.getAttribute('alt')||'')) img.style.display='none';
        img.addEventListener('error',function(){ img.style.display='none'; });
        if(img.complete && img.naturalWidth===0) img.style.display='none';
      });
    });

    // 2) header shadow on scroll
    safe(function(){
      var h=document.querySelector('header,.elementor-location-header,.site-header'); if(!h) return;
      var f=function(){ h.classList.toggle('scrolled', scrollY>12); };
      addEventListener('scroll',f,{passive:true}); f();
    });

    // 3) logo links home (clone had href="")
    safe(function(){
      document.querySelectorAll('a[href=""] img, a[href="#"] img').forEach(function(img){
        var src=(img.getAttribute('src')||'');
        if(/logo/i.test(src) || img.closest('header,.elementor-location-header')) img.closest('a').setAttribute('href','/');
      });
    });

    // 4) nav dropdowns — click to open (robust; CSS shows .pr-open submenus)
    safe(function(){
      var nav=document.querySelector('.elementor-nav-menu--main') || document;
      function closeAll(scope){ (scope||nav).querySelectorAll('.menu-item-has-children.pr-open').forEach(function(li){li.classList.remove('pr-open');}); }
      nav.querySelectorAll('.menu-item-has-children > a').forEach(function(a){
        a.addEventListener('click', function(e){
          var li=a.parentNode, sub=li.querySelector(':scope > .sub-menu');
          if(!sub) return;                      // no children → normal link
          e.preventDefault(); e.stopPropagation();
          var open=li.classList.contains('pr-open');
          // close siblings at this level
          Array.prototype.forEach.call(li.parentNode.children, function(s){ if(s!==li){ s.classList.remove('pr-open'); closeAll(s); } });
          li.classList.toggle('pr-open', !open);
        });
      });
      document.addEventListener('click', function(){ closeAll(); });
      document.addEventListener('keydown', function(e){ if(e.key==='Escape') closeAll(); });
    });

    // 5) count-up numbers (Elementor counters)
    safe(function(){
      var nums=document.querySelectorAll('.elementor-counter-number'); if(!nums.length||!('IntersectionObserver'in window)) return;
      var fmt=function(n,delim,dec){ var s=(dec?n.toFixed(dec):Math.round(n).toString()); return delim?s.replace(/\B(?=(\d{3})+(?!\d))/g,delim):s; };
      var io=new IntersectionObserver(function(es){es.forEach(function(en){ if(!en.isIntersecting) return; io.unobserve(en.target);
        var el=en.target, to=parseFloat(el.getAttribute('data-to-value')||el.textContent)||0,
            from=parseFloat(el.getAttribute('data-from-value')||0), dur=parseInt(el.getAttribute('data-duration')||1800,10),
            delim=el.getAttribute('data-delimiter')||'', dec=(String(to).split('.')[1]||'').length, t0=null;
        if(reduce){ el.textContent=fmt(to,delim,dec); return; }
        (function step(ts){ t0=t0||ts; var p=Math.min((ts-t0)/dur,1), v=from+(to-from)*(1-Math.pow(1-p,3));
          el.textContent=fmt(v,delim,dec); if(p<1) requestAnimationFrame(step); })(performance.now());
      });},{threshold:.4});
      nums.forEach(function(n){ io.observe(n); });
    });

    // 6) video lightbox (mahafuj/Elementor play buttons)
    safe(function(){
      var triggers=document.querySelectorAll('.mvp-play-button,.mvp-play-wrap,.elementor-custom-embed-play,[class*="video-play"],a[href*="youtu"],a[href*="vimeo"]');
      if(!triggers.length) return;
      // find a video id on the page
      var id=null, src=null, html=document.documentElement.innerHTML;
      var m=html.match(/(?:youtu\.be\/|youtube\.com\/(?:embed\/|watch\?v=))([\w-]{6,})/); if(m) id=m[1];
      var vm=html.match(/vimeo\.com\/(\d+)/);
      if(id) src='https://www.youtube.com/embed/'+id+'?autoplay=1&rel=0';
      else if(vm) src='https://player.vimeo.com/video/'+vm[1]+'?autoplay=1';
      if(!src) return;
      var open=function(e){ e.preventDefault(); e.stopPropagation();
        var o=document.createElement('div'); o.className='pr-vmodal';
        o.innerHTML='<div class="pr-vmodal-inner"><button class="pr-vmodal-close" aria-label="Close">&times;</button><iframe allow="autoplay; fullscreen" allowfullscreen src="'+src+'"></iframe></div>';
        document.body.appendChild(o); requestAnimationFrame(function(){o.classList.add('pr-show');});
        var close=function(){ o.classList.remove('pr-show'); setTimeout(function(){o.remove();},250); };
        o.addEventListener('click',function(ev){ if(ev.target===o||ev.target.classList.contains('pr-vmodal-close')) close(); });
        document.addEventListener('keydown',function k(ev){ if(ev.key==='Escape'){close();document.removeEventListener('keydown',k);} });
      };
      triggers.forEach(function(t){ t.style.cursor='pointer'; t.addEventListener('click',open); });
    });

    // 7) testimonials — inject 5 stars + hover-lift
    safe(function(){
      var cards=document.querySelectorAll('.elementor-testimonial, .elementor-widget-testimonial .elementor-widget-container, [class*="testimonial"][class*="item"], .elementor-testimonial__content');
      var seen=new Set();
      cards.forEach(function(c){
        var card=c.closest('.elementor-widget')||c; if(seen.has(card)) return; seen.add(card);
        if(card.querySelector('.pr-stars')) return;
        card.classList.add('pr-tcard');
        var stars=document.createElement('div'); stars.className='pr-stars'; stars.setAttribute('aria-label','5 out of 5 stars');
        stars.innerHTML='★★★★★';
        var host=card.querySelector('.elementor-testimonial__text, .elementor-testimonial__content')||card.firstElementChild||card;
        host.parentNode.insertBefore(stars, host);
      });
    });

    // 8) hero overlay boxes — blend solid blocks into the image
    safe(function(){
      var hero=document.querySelector('.elementor-section, section'); if(!hero) return;
      var widgets=hero.querySelectorAll('.elementor-widget-heading,.elementor-widget-text-editor,.elementor-widget-form,form');
      widgets.forEach(function(w){
        var bg=getComputedStyle(w.querySelector('.elementor-widget-container')||w).backgroundColor;
        var m=bg && bg.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/);
        if(!m) return; var a=m[4]===undefined?1:parseFloat(m[4]);
        var dark=(+m[1]+ +m[2]+ +m[3])/3 < 170;
        if(a>=0.95 && dark){ // opaque dark block sitting over the hero
          (w.querySelector('form')||w.querySelector('.elementor-widget-container')) ?
            w.classList.add(w.querySelector('form')?'pr-hero-form':'pr-hero-overlay') : w.classList.add('pr-hero-overlay');
        }
      });
    });

    // 9) scroll-reveal
    if(reduce || !('IntersectionObserver' in window)) return;
    safe(function(){
      var sel='.elementor-widget-heading,.elementor-widget-text-editor,.elementor-widget-image,.elementor-widget-image-box,.elementor-widget-icon-box,.elementor-widget-button,.pr-tcard,.entry-content > *,.wp-block-image';
      var els=[].slice.call(document.querySelectorAll(sel)).filter(function(el){
        if(el.closest('header,footer,nav,.elementor-location-header,.elementor-location-footer')) return false;
        var r=el.getBoundingClientRect(); return r.top>80 && r.height<innerHeight*1.4;
      });
      els.forEach(function(el,i){ el.classList.add('pr-reveal'); var d=i%3; if(d) el.classList.add('pr-reveal-d'+d); });
      var io=new IntersectionObserver(function(es){es.forEach(function(e){ if(e.isIntersecting){e.target.classList.add('pr-in');io.unobserve(e.target);} });},{rootMargin:'0px 0px -8% 0px',threshold:.08});
      els.forEach(function(el){ io.observe(el); });
    });
  });
})();
