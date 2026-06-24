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

    // 8) modern hero — replace the boxy text + non-functional inline CF7 form on the
    //    cloned .page-banner with clean text + a "Free Consultation" CTA that opens a modal.
    safe(function(){
      var banner=document.querySelector('.page-banner'); if(!banner) return;
      banner.classList.add('pr-hero');
      // drop the inline form column (it can't submit on a static deploy anyway)
      var form=banner.querySelector('.banner-form');
      if(form){ var fc=form.closest('[class*="col-"]'); if(fc) fc.classList.add('pr-hide'); else form.style.display='none'; }
      // inject the CTA cluster into the content column
      var content=banner.querySelector('.banner-content');
      if(content && !content.querySelector('.pr-hero-cta')){
        var cta=document.createElement('div'); cta.className='pr-hero-cta';
        cta.innerHTML='<button type="button" class="pr-cta-btn" data-pr-open-modal>Free Consultation</button>'+
          '<a class="pr-cta-call" href="tel:+17707275550"><span>Call 24/7 · Free Case Review</span><strong>(770) 727-5550</strong></a>';
        content.appendChild(cta);
      }
    });

    // 8b) consultation modal — built once, opened by any [data-pr-open-modal] trigger.
    safe(function(){
      if(document.querySelector('.pr-modal')) return;
      var m=document.createElement('div'); m.className='pr-modal'; m.setAttribute('aria-hidden','true');
      m.innerHTML='<div class="pr-modal-card" role="dialog" aria-modal="true" aria-label="Request a free consultation">'+
        '<button class="pr-modal-x" type="button" aria-label="Close">&times;</button>'+
        '<h3>Request a Free Consultation</h3>'+
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
      document.addEventListener('keydown',function(e){ if(e.key==='Escape'&&m.classList.contains('pr-show')) close(); });
      m.querySelector('.pr-modal-form').addEventListener('submit',function(e){
        e.preventDefault(); var fd=new FormData(e.target);
        var body=encodeURIComponent('Name: '+fd.get('name')+'\nPhone: '+fd.get('phone')+'\nEmail: '+fd.get('email')+'\n\n'+fd.get('message'));
        var subj=encodeURIComponent('Free Consultation Request — '+fd.get('name'));
        window.location.href='mailto:cade@westgalawyer.com?subject='+subj+'&body='+body;
      });
    });

    // 10) Google-review social proof — a star badge in the hero + a conversion band
    //     before the footer on inner clone pages. Numbers are verified (see
    //     practice.json reviews): 4.9★, 1,000+ reviews (Birdeye aggregate, Google-dominant).
    safe(function(){
      var RATING='4.9', COUNT='1,000+';
      var starsHTML='<span class="pr-rev-stars">★★★★★</span>';
      // a) hero badge (under the CTA cluster)
      var ctaWrap=document.querySelector('.pr-hero-cta');
      if(ctaWrap && !document.querySelector('.pr-rev-badge')){
        var b=document.createElement('div'); b.className='pr-rev-badge';
        b.innerHTML=starsHTML+'<span class="pr-rev-txt"><strong>'+RATING+'</strong> · '+COUNT+' <i class="fab fa-google"></i> Google reviews</span>';
        ctaWrap.parentNode.insertBefore(b, ctaWrap.nextSibling);
      }
      // b) pre-footer conversion band (inner clone pages only — they have .page-banner)
      var foot=document.querySelector('footer.pl-foot');
      if(foot && document.querySelector('.page-banner') && !document.querySelector('.pr-rev-band')){
        var band=document.createElement('section'); band.className='pr-rev-band';
        band.innerHTML='<div class="pr-rev-band-in">'+
          '<div class="pr-rev-band-rate">'+starsHTML+'<span><strong>'+RATING+'</strong> rating · '+COUNT+' <i class="fab fa-google"></i> Google reviews</span></div>'+
          '<div class="pr-rev-band-cta"><span class="pr-rev-band-h">Trusted by west Georgia. Let’s talk about your case.</span>'+
          '<button type="button" class="pr-cta-btn" data-pr-open-modal>Free Consultation</button></div>'+
          '</div>';
        foot.parentNode.insertBefore(band, foot);
      }
    });

    // 11) service-page enrichment — break up the wall of text with a category-relevant
    //     image, a lead paragraph, accented headings, and a mid-content callout. Varied
    //     per page (image variant + side + accent) by a slug hash so pages don't all match.
    safe(function(){
      if(!document.querySelector('.page-banner')) return;            // inner pages only
      var col=null, best=0;
      document.querySelectorAll('.col-sm-8').forEach(function(c){
        if(c.closest('.banner-form,.page-banner,footer')) return;
        var ps=c.querySelectorAll(':scope > p'); var n=0; ps.forEach(function(p){n+=p.textContent.trim().length;});
        if(n>best){best=n;col=c;}
      });
      if(!col) return;
      var ps=[].slice.call(col.querySelectorAll(':scope > p')).filter(function(p){return p.textContent.trim().length>40;});
      if(ps.length<4 || col.dataset.prEnriched) return;
      col.dataset.prEnriched='1';

      // category from slug
      var slug=location.pathname.toLowerCase();
      var MAP=[['truck','truck-accident'],['motorcycle','motorcycle'],['pedestrian','pedestrian'],
        ['dog','dog-bite'],['slip','slip-and-fall'],['fall','slip-and-fall'],['nursing','nursing-home'],
        ['workers','workers-compensation'],['workman','workers-compensation'],['social-security','social-security'],
        ['disability','social-security'],['wrongful','wrongful-death'],['mass-tort','mass-torts'],['drug','mass-torts'],
        ['catastrophic','catastrophic'],['brain','catastrophic'],['spinal','catastrophic'],['malpractice','injury'],
        ['medical','injury'],['car','car-accident'],['auto','car-accident'],['wreck','car-accident'],['bus','car-accident'],
        ['divorce','legal'],['custody','legal'],['child-support','legal'],['family','legal'],['adoption','legal'],
        ['criminal','courthouse'],['dui','courthouse'],['assault','courthouse'],['charge','courthouse'],['injury','injury']];
      var cat='legal';
      for(var i=0;i<MAP.length;i++){ if(slug.indexOf(MAP[i][0])>-1){ cat=MAP[i][1]; break; } }

      // stable hash → variety
      var h=0; for(var j=0;j<slug.length;j++){ h=((h<<5)-h+slug.charCodeAt(j))|0; }
      h=Math.abs(h);
      var variant=(h%2)+1;                  // -1 or -2 image
      var side=(h>>1)%2 ? 'right':'left';   // float side
      col.classList.add('pr-enriched','pr-acc-'+(h%3)); // 3 heading-accent flavors

      // lead paragraph
      if(ps[0]) ps[0].classList.add('pr-lead');

      // category image — float before the first subheading (or after para 2)
      var anchor=col.querySelector(':scope > h2, :scope > h3') || ps[2] || ps[1];
      if(anchor){
        var fig=document.createElement('figure');
        fig.className='pr-figure pr-figure--'+side;
        fig.innerHTML='<img src="/images/stock/'+cat+'-'+variant+'.jpg" alt="" loading="lazy" decoding="async">';
        anchor.parentNode.insertBefore(fig, anchor);
      }

      // mid-content callout CTA (before a heading in the lower half)
      var heads=col.querySelectorAll(':scope > h2, :scope > h3');
      if(heads.length>=2){
        var target=heads[Math.min(heads.length-1, Math.floor(heads.length/2)+ (h%2))];
        if(target && !col.querySelector('.pr-inline-cta')){
          var box=document.createElement('div'); box.className='pr-inline-cta';
          box.innerHTML='<div><strong>Hurt and not sure what your case is worth?</strong><span>Get a free, confidential review — no obligation.</span></div>'+
            '<button type="button" class="pr-cta-btn" data-pr-open-modal>Free Consultation</button>';
          target.parentNode.insertBefore(box, target);
        }
      }
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
