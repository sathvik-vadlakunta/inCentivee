import type { APIRoute } from 'astro'

export const prerender = false

interface ContactFormData {
  name: string
  email: string
  phone: string
  message?: string
  site?: string
}

function validateEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
}

function validatePhone(phone: string): boolean {
  const digits = phone.replace(/\D/g, '')
  return digits.length >= 7 && digits.length <= 15
}

function esc(s: string): string {
  return s.replace(/[<>&]/g, (c) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' }[c] as string))
}

export const POST: APIRoute = async ({ request, locals }) => {
  try {
    const body = (await request.json()) as Partial<ContactFormData>
    const errors: string[] = []

    if (!body.name || body.name.trim().length === 0) errors.push('Name is required.')
    if (!body.email || !validateEmail(body.email)) errors.push('A valid email address is required.')
    if (!body.phone || !validatePhone(body.phone)) errors.push('A valid phone number is required.')

    if (errors.length > 0) {
      return json({ success: false, errors }, 400)
    }

    const submission: ContactFormData = {
      name: body.name!.trim(),
      email: body.email!.trim(),
      phone: body.phone!.trim(),
      message: body.message?.trim() || '',
      site: body.site?.trim() || 'Parian Lawyers',
    }

    console.log('[contact-form]', JSON.stringify(submission))

    // Env can come from Cloudflare runtime (locals.runtime.env) or import.meta.env.
    const env: Record<string, string | undefined> = {
      ...(import.meta.env as unknown as Record<string, string | undefined>),
      ...((locals as { runtime?: { env?: Record<string, string> } })?.runtime?.env || {}),
    }
    // Fallbacks use the already-verified practicerank.ai sender so delivery never
    // breaks if a secret is missing. Swap CONTACT_FROM to the customer's own domain
    // once it's verified in Resend (see scripts/verify_customer_email_domain.py).
    const RESEND_API_KEY = env.RESEND_API_KEY
    const CONTACT_TO = env.CONTACT_TO || 'cade@callcadenow.com'
    const CONTACT_FROM = env.CONTACT_FROM || 'Parian Lawyers <leads@practicerank.ai>'

    // Deliver via Resend when configured; otherwise log-only (still succeeds) so the
    // form works the moment the API key + verified domain are added.
    if (RESEND_API_KEY) {
      const { Resend } = await import('resend')
      const resend = new Resend(RESEND_API_KEY)
      const { error } = await resend.emails.send({
        from: CONTACT_FROM,
        to: [CONTACT_TO],
        replyTo: submission.email,
        subject: `New consultation request — ${submission.name}`,
        html:
          `<h2>New Consultation Request</h2>` +
          `<p><strong>Name:</strong> ${esc(submission.name)}</p>` +
          `<p><strong>Email:</strong> ${esc(submission.email)}</p>` +
          `<p><strong>Phone:</strong> ${esc(submission.phone)}</p>` +
          `<p><strong>Message:</strong> ${esc(submission.message || '(none)')}</p>` +
          `<p style="color:#888">Source: ${esc(submission.site || '')}</p>`,
      })
      if (error) {
        console.error('[contact-form] resend error', error)
        return json({ success: false, errors: ['Could not send right now. Please call us.'] }, 502)
      }
    }

    return json({ success: true, message: 'Your message has been received.' }, 200)
  } catch {
    return json({ success: false, errors: ['Invalid request. Please try again.'] }, 400)
  }
}

function json(data: unknown, status: number): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}
