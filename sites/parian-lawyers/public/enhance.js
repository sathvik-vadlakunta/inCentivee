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

    // 7) testimonials — inject a 5-star row at the top of each card
    safe(function(){
      // their custom template card is .testimonails-box; also support Elementor widget
      var cards=document.querySelectorAll('.testimonails-box, .elementor-testimonial');
      cards.forEach(function(card){
        if(card.querySelector('.pr-stars')) return;
        card.classList.add('pr-tcard');
        var stars=document.createElement('div'); stars.className='pr-stars'; stars.setAttribute('aria-label','5 out of 5 stars');
        stars.innerHTML='★★★★★';
        card.insertBefore(stars, card.firstChild);
      });
    });

    // (hero CTA, review badge/band, and service-page enrichment are now baked in at
    //  BUILD time — see src/lib/enrich.ts — so they're in the HTML on first paint and
    //  there's no flash. Only the modal + scroll-reveal remain at runtime below.)

    // 8b) consultation modal — built once, opened by any [data-pr-open-modal] trigger.
    safe(function(){
      if(document.querySelector('.pr-modal')) return;
      var m=document.createElement('div'); m.className='pr-modal'; m.setAttribute('aria-hidden','true');
      m.innerHTML='<div class="pr-modal-card" role="dialog" aria-modal="true" aria-labelledby="prModalTitle">'+
        '<button class="pr-modal-x" type="button" aria-label="Close consultation form">&times;</button>'+
        '<h3 id="prModalTitle">Request a Free Consultation</h3>'+
        '<p class="pr-modal-sub">Tell us what happened — we’ll review your case at no cost. Or call <a href="tel:+17707275550">(770) 727-5550</a>.</p>'+
        '<form class="pr-modal-form">'+
          '<label>Full name<input name="name" autocomplete="name" required></label>'+
          '<div class="pr-modal-row"><label>Phone<input name="phone" type="tel" autocomplete="tel" required></label>'+
          '<label>Email<input name="email" type="email" autocomplete="email" required></label></div>'+
          '<label>How can we help?<textarea name="message" rows="4" required></textarea></label>'+
          '<button type="submit" class="pr-cta-btn pr-modal-submit">Send Message</button>'+
          '<p class="pr-modal-fine">Submitting this form does not create an attorney-client relationship.</p>'+
        '</form></div>';
      document.body.appendChild(m);
      var lastFocus=null;
      var open=function(){ lastFocus=document.activeElement; m.classList.add('pr-show'); m.setAttribute('aria-hidden','false'); document.body.style.overflow='hidden'; var f=m.querySelector('input'); if(f) setTimeout(function(){f.focus();},60); };
      var close=function(){ m.classList.remove('pr-show'); m.setAttribute('aria-hidden','true'); document.body.style.overflow=''; if(lastFocus&&lastFocus.focus) lastFocus.focus(); };
      document.addEventListener('click',function(e){ if(e.target.closest('[data-pr-open-modal]')){ e.preventDefault(); open(); } });
      m.addEventListener('click',function(e){ if(e.target===m||e.target.closest('.pr-modal-x')) close(); });
      // keyboard: Esc closes; Tab is trapped within the dialog (a11y)
      document.addEventListener('keydown',function(e){
        if(!m.classList.contains('pr-show')) return;
        if(e.key==='Escape'){ close(); return; }
        if(e.key==='Tab'){
          var f=m.querySelectorAll('a[href],button,input,textarea,select');
          f=[].slice.call(f).filter(function(el){return !el.disabled&&el.offsetParent!==null;});
          if(!f.length) return;
          var first=f[0], last=f[f.length-1];
          if(e.shiftKey && document.activeElement===first){ e.preventDefault(); last.focus(); }
          else if(!e.shiftKey && document.activeElement===last){ e.preventDefault(); first.focus(); }
        }
      });
      m.querySelector('.pr-modal-form').addEventListener('submit',function(e){
        e.preventDefault();
        var form=e.target, btn=form.querySelector('.pr-modal-submit'), fd=new FormData(form);
        var payload={name:fd.get('name'),phone:fd.get('phone'),email:fd.get('email'),message:fd.get('message'),site:'Parian Lawyers (consultation modal)'};
        var old=btn.textContent; btn.disabled=true; btn.textContent='Sending…';
        fetch('/api/contact',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
          .then(function(r){ if(!r.ok) throw new Error('fail');
            form.innerHTML='<p class="pr-modal-fine" style="font-size:15px;color:#1a1e2e">Thank you — we received your request and will reach out shortly. For immediate help, call <a href="tel:+17707275550">(770) 727-5550</a>.</p>';
          })
          .catch(function(){ btn.disabled=false; btn.textContent=old;
            var err=form.querySelector('.pr-modal-err');
            if(!err){ err=document.createElement('p'); err.className='pr-modal-fine pr-modal-err'; err.style.color='#c0392b'; form.appendChild(err); }
            err.textContent='Something went wrong — please call (770) 727-5550.';
          });
      });
    });

    // (hero entrance + ken-burns are now pure CSS keyed on .page-banner / .bio / .sch
    //  so they run on first paint — see enhance.css "hero entrance + subtle motion".)

    // (stray-apostrophe cleanup moved to BUILD time — see fixApostrophes() in
    //  src/pages/[...path].astro — so there's no runtime text-shift flash.)

    // 9) scroll-reveal
    if(reduce || !('IntersectionObserver' in window)) return;
    safe(function(){
      var sel=[
        '.elementor-widget-heading','.elementor-widget-text-editor','.elementor-widget-image',
        '.elementor-widget-image-box','.elementor-widget-icon-box','.elementor-widget-button',
        '.pr-tcard','.entry-content > *','.wp-block-image',
        // service-page enrichment + cross-site sections
        '.pr-figure','.pr-enriched > h2','.pr-enriched > h3','.pr-inline-cta','.pr-rev-band',
        '.bio__quote','.bio__award','.bio__prose > p','.bio__close',
        '.sch__gap-card','.sch__stat','.sch__award-card','.sch__elig-item','.sch__req-card','.sch__apply .sch__wrap'
      ].join(',');
      var els=[].slice.call(document.querySelectorAll(sel)).filter(function(el){
        if(el.closest('header,footer,nav,.elementor-location-header,.elementor-location-footer,.pr-hero')) return false;
        var r=el.getBoundingClientRect(); return r.top>80 && r.height<innerHeight*1.6;
      });
      els.forEach(function(el,i){ el.classList.add('pr-reveal'); var d=i%3; if(d) el.classList.add('pr-reveal-d'+d); });
      var io=new IntersectionObserver(function(es){es.forEach(function(e){ if(e.isIntersecting){e.target.classList.add('pr-in');io.unobserve(e.target);} });},{rootMargin:'0px 0px -8% 0px',threshold:.08});
      els.forEach(function(el){ io.observe(el); });
    });
  });
})();
