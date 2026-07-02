import type { APIRoute } from 'astro'
import practice from '@data/practice.json'

export const prerender = false

export const POST: APIRoute = async ({ request, locals }) => {
  try {
    // ContactForm.astro submits JSON; fall back to form-encoded just in case.
    const ct = request.headers.get('content-type') || ''
    let body: Record<string, string> = {}
    if (ct.includes('application/json')) {
      body = await request.json()
    } else {
      const data = await request.formData()
      body = Object.fromEntries([...data.entries()].map(([k, v]) => [k, String(v)]))
    }
    const name = String(body.name || '').trim()
    const phone = String(body.phone || '').trim()
    const email = String(body.email || '').trim()
    const message = String(body.message || '').trim()

    if (!name || (!phone && !email)) {
      return new Response(
        JSON.stringify({ ok: false, error: 'Please include your name and a phone number or email.' }),
        { status: 400, headers: { 'Content-Type': 'application/json' } },
      )
    }

    // Cloudflare Pages exposes bindings/secrets via locals.runtime.env
    const key = (locals as any)?.runtime?.env?.RESEND_API_KEY || import.meta.env.RESEND_API_KEY
    if (key) {
      const resp = await fetch('https://api.resend.com/emails', {
        method: 'POST',
        headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          from: 'Healing Hands PT Website <noreply@practicerank.ai>',
          to: [practice.email],
          reply_to: email || undefined,
          subject: `New website inquiry — ${name}`,
          text: `New inquiry from the Healing Hands Physical Therapy website:\n\nName: ${name}\nPhone: ${phone || '—'}\nEmail: ${email || '—'}\n\nMessage:\n${message || '—'}`,
        }),
      })
      if (!resp.ok) {
        // Don't lose the lead silently — surface a soft failure so the UI can offer phone/email.
        return new Response(
          JSON.stringify({ ok: false, error: 'We could not send your message. Please call us — we\'d love to help.' }),
          { status: 502, headers: { 'Content-Type': 'application/json' } },
        )
      }
    }

    return new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  } catch {
    return new Response(
      JSON.stringify({ ok: false, error: 'Something went wrong. Please call us at ' + practice.phone + '.' }),
      { status: 500, headers: { 'Content-Type': 'application/json' } },
    )
  }
}
