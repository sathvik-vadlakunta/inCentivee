// Build-time content enrichment for cloned pages — the same transforms enhance.js
// used to do at runtime (hero CTA + Google-review badge, service-page feature image +
// lead paragraph + heading accents + mid-content CTA), now baked into the HTML so
// there's no flash. Returns the enriched body (review band appended) — it renders
// before the SiteFooter, exactly where the runtime version inserted it.
import { parse, type HTMLElement } from 'node-html-parser'

const PHONE = '(770) 727-5550'
const TEL = '+17707275550'
const RATING = '4.9'
const COUNT = '1,000+'
const STARS = '<span class="pr-rev-stars">★★★★★</span>'

const REV_BADGE =
  `<div class="pr-rev-badge">${STARS}<span class="pr-rev-txt"><strong>${RATING}</strong> · ${COUNT} <i class="fab fa-google"></i> Google reviews</span></div>`

const HERO_CTA =
  `<div class="pr-hero-cta">` +
  `<button type="button" class="pr-cta-btn" data-pr-open-modal>Free Consultation</button>` +
  `<a class="pr-cta-call" href="tel:${TEL}"><span>Call 24/7 · Free Case Review</span><strong>${PHONE}</strong></a>` +
  `</div>` +
  REV_BADGE

const REV_BAND =
  `<section class="pr-rev-band"><div class="pr-rev-band-in">` +
  `<div class="pr-rev-band-rate">${STARS}<span><strong>${RATING}</strong> rating · ${COUNT} <i class="fab fa-google"></i> Google reviews</span></div>` +
  `<div class="pr-rev-band-cta"><span class="pr-rev-band-h">Trusted by west Georgia. Let’s talk about your case.</span>` +
  `<button type="button" class="pr-cta-btn" data-pr-open-modal>Free Consultation</button></div>` +
  `</div></section>`

const INLINE_CTA =
  `<div class="pr-inline-cta"><div><strong>Hurt and not sure what your case is worth?</strong>` +
  `<span>Get a free, confidential review — no obligation.</span></div>` +
  `<button type="button" class="pr-cta-btn" data-pr-open-modal>Free Consultation</button></div>`

// slug keyword -> stock image key (mirror of enhance.js)
const CAT_MAP: [string, string][] = [
  ['truck', 'truck-accident'], ['motorcycle', 'motorcycle'], ['pedestrian', 'pedestrian'],
  ['dog', 'dog-bite'], ['slip', 'slip-and-fall'], ['fall', 'slip-and-fall'], ['nursing', 'nursing-home'],
  ['workers', 'workers-compensation'], ['workman', 'workers-compensation'], ['social-security', 'social-security'],
  ['disability', 'social-security'], ['wrongful', 'wrongful-death'], ['mass-tort', 'mass-torts'], ['drug', 'mass-torts'],
  ['catastrophic', 'catastrophic'], ['brain', 'catastrophic'], ['spinal', 'catastrophic'], ['malpractice', 'injury'],
  ['medical', 'injury'], ['car', 'car-accident'], ['auto', 'car-accident'], ['wreck', 'car-accident'], ['bus', 'car-accident'],
  ['divorce', 'legal'], ['custody', 'legal'], ['child-support', 'legal'], ['family', 'legal'], ['adoption', 'legal'],
  ['criminal', 'courthouse'], ['dui', 'courthouse'], ['assault', 'courthouse'], ['charge', 'courthouse'], ['injury', 'injury'],
]
const INFO_RE = /(^|\/)(about-us|what-to-expect|who-we-represent|areas-served|practice-areas|our-team|choosing-the|awards-honors|scholarship|testimonials|client-testimonials|contact)(\/|$)/

function hash(s: string): number {
  let h = 0
  for (let i = 0; i < s.length; i++) h = ((h << 5) - h + s.charCodeAt(i)) | 0
  return Math.abs(h)
}
const directChildren = (el: HTMLElement, tag: string) =>
  el.childNodes.filter((n): n is HTMLElement => (n as HTMLElement).tagName === tag.toUpperCase())

export function enrich(bodyHtml: string, slugPath: string): string {
  const root = parse(bodyHtml, { comment: true })
  const banner = root.querySelector('.page-banner')
  if (!banner) return bodyHtml // only inner clone pages get enriched

  // 1) hero: hide the dead inline form column, add CTA + review badge to the content
  const form = banner.querySelector('.banner-form')
  if (form) {
    let col: HTMLElement | null = form as HTMLElement
    while (col && !(col.classList && [...col.classList.values()].some((c) => c.startsWith('col-')))) col = col.parentNode as HTMLElement
    ;(col || (form as HTMLElement)).classList.add('pr-hide')
  }
  const content = banner.querySelector('.banner-content')
  if (content && !content.querySelector('.pr-hero-cta')) content.insertAdjacentHTML('beforeend', HERO_CTA)

  // 2) service-page enrichment — feature image + lead + heading accents + mid CTA
  const slug = ('/' + slugPath).toLowerCase()
  const cols = root.querySelectorAll('.col-sm-8').filter((c) => {
    let p = c.parentNode as HTMLElement | null
    while (p) {
      const cls = p.classList ? [...p.classList.values()] : []
      if (cls.includes('banner-form') || cls.includes('page-banner') || p.tagName === 'FOOTER') return false
      p = p.parentNode as HTMLElement | null
    }
    return true
  })
  let col: HTMLElement | null = null
  let best = 0
  for (const c of cols) {
    const n = directChildren(c, 'p').reduce((a, p) => a + p.text.trim().length, 0)
    if (n > best) { best = n; col = c }
  }
  if (col) {
    const ps = directChildren(col, 'p').filter((p) => p.text.trim().length > 40)
    if (ps.length >= 4) {
      const h = hash(slug)
      const variant = (h % 2) + 1
      const side = (h >> 1) % 2 ? 'right' : 'left'
      col.classList.add('pr-enriched', 'pr-acc-' + (h % 3))
      ps[0].classList.add('pr-lead')

      let cat = 'legal'
      for (const [k, v] of CAT_MAP) if (slug.indexOf(k) > -1) { cat = v; break }
      const skipImg = INFO_RE.test(slug)
      const heads = col.childNodes.filter((n): n is HTMLElement => (n as HTMLElement).tagName === 'H2' || (n as HTMLElement).tagName === 'H3')
      const anchor = heads[0] || ps[2] || ps[1]
      if (anchor && !skipImg) {
        anchor.insertAdjacentHTML('beforebegin',
          `<figure class="pr-figure pr-figure--${side}"><img src="/images/stock/${cat}-${variant}.jpg" alt="" loading="lazy" decoding="async"></figure>`)
      }
      if (heads.length >= 2) {
        const target = heads[Math.min(heads.length - 1, Math.floor(heads.length / 2) + (h % 2))]
        if (target && !col.querySelector('.pr-inline-cta')) target.insertAdjacentHTML('beforebegin', INLINE_CTA)
      }
    }
  }

  // 3) pre-footer review band — appended so it renders just before the SiteFooter
  return root.toString() + REV_BAND
}
