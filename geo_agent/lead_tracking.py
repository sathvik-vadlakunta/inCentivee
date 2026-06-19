"""Client-side lead-tracking snippet for customer sites.

The gap this closes: GA4 can only report leads if the site actually *fires* lead
events. This paste-once snippet auto-wires the three signals that matter for a
local business — phone-number clicks, form submissions, and booking/CTA clicks —
into GA4 events whose names match ``ga4_client.DEFAULT_CONVERSION_EVENTS``
(``phone_click`` / ``form_submit`` / ``appointment_request``). Once installed,
``track_conversions`` pulls them into ``conversions_daily`` and the weekly report
shows real leads (calls + forms), not just traffic.

Platform-agnostic: it fires to ``gtag`` (GA4) if present, otherwise pushes to the
GTM ``dataLayer`` — so it works whether the site has GA4 directly or via GTM.
"""

from __future__ import annotations

# The snippet. Self-contained, no external file, safe to paste into any site's
# head/custom-code or a GTM Custom HTML tag. Idempotent (guards re-init).
LEAD_TRACKER_JS = """<!-- PracticeRank Lead Tracking — fires phone_click / form_submit / appointment_request -->
<script>
(function () {
  if (window.__prLeadsInit) return; window.__prLeadsInit = true;
  function fire(name, params) {
    try {
      if (typeof window.gtag === 'function') { window.gtag('event', name, params || {}); }
      else { (window.dataLayer = window.dataLayer || []).push(Object.assign({ event: name }, params || {})); }
    } catch (e) {}
  }
  var BOOK = /book|appointment|schedule|request|consult|get started|free quote|estimate|reserve|contact us/i;
  document.addEventListener('click', function (ev) {
    var t = ev.target;
    if (!t || !t.closest) return;
    var tel = t.closest('a[href^="tel:"]');
    if (tel) { fire('phone_click', { phone: (tel.getAttribute('href') || '').replace('tel:', '') }); return; }
    var cta = t.closest('[data-pr-cta], a[href], button');
    if (cta) {
      var label = (cta.getAttribute('aria-label') || cta.textContent || '').trim();
      if (cta.hasAttribute('data-pr-cta') || BOOK.test(label)) {
        fire('appointment_request', { label: label.slice(0, 60) });
      }
    }
  }, true);
  document.addEventListener('submit', function (ev) {
    var f = ev.target || {};
    var name = (f.getAttribute && (f.getAttribute('name') || f.getAttribute('id'))) || 'form';
    fire('form_submit', { form: String(name).slice(0, 60) });
  }, true);
})();
</script>"""

# Per-platform install steps (rendered in the dashboard "How to install" modal).
INSTALL_STEPS = {
    "gtm": [
        "In Google Tag Manager, go to <b>Tags → New → Custom HTML</b>.",
        "Paste the snippet, set trigger to <b>All Pages</b>, name it 'PracticeRank Lead Tracking', Save.",
        "Click <b>Submit / Publish</b> to push the container live.",
    ],
    "webflow": [
        "Site Settings → <b>Custom Code</b> → <b>Footer Code</b> (or Head).",
        "Paste the snippet and Save.",
        "<b>Publish</b> the site.",
    ],
    "squarespace": [
        "Settings → <b>Developer Tools → Code Injection</b> → <b>Footer</b>.",
        "Paste the snippet and Save. (Code Injection needs a Business plan or higher.)",
    ],
    "wordpress": [
        "Use a header/footer-scripts plugin (or the theme's custom-code area).",
        "Paste the snippet into the <b>Footer</b> scripts and Save.",
    ],
    "managed": [
        "For sites we host: we add the snippet to the site layout — no client action needed.",
    ],
}


def lead_tracker_snippet() -> str:
    """The paste-once tracking snippet (static)."""
    return LEAD_TRACKER_JS
