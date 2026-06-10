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

export const POST: APIRoute = async ({ request }) => {
  try {
    const body = (await request.json()) as Partial<ContactFormData>

    const errors: string[] = []

    if (!body.name || body.name.trim().length === 0) {
      errors.push('Name is required.')
    }

    if (!body.email || !validateEmail(body.email)) {
      errors.push('A valid email address is required.')
    }

    if (!body.phone || !validatePhone(body.phone)) {
      errors.push('A valid phone number is required.')
    }

    if (errors.length > 0) {
      return new Response(JSON.stringify({ success: false, errors }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      })
    }

    const submission: ContactFormData = {
      name: body.name!.trim(),
      email: body.email!.trim(),
      phone: body.phone!.trim(),
      message: body.message?.trim() || '',
      site: body.site?.trim() || '',
    }

    // Log the submission (visible in Cloudflare Workers logs)
    console.log('[contact-form]', JSON.stringify(submission))

    // -------------------------------------------------------
    // Resend integration (uncomment when ready)
    // -------------------------------------------------------
    // import { Resend } from 'resend'
    //
    // const resend = new Resend(import.meta.env.RESEND_API_KEY)
    //
    // await resend.emails.send({
    //   from: 'SoJo Dental <noreply@sojodental.com>',
    //   to: ['frontdesk@sojodental.com'],
    //   replyTo: submission.email,
    //   subject: `New contact form submission from ${submission.name}`,
    //   html: `
    //     <h2>New Contact Form Submission</h2>
    //     <p><strong>Name:</strong> ${submission.name}</p>
    //     <p><strong>Email:</strong> ${submission.email}</p>
    //     <p><strong>Phone:</strong> ${submission.phone}</p>
    //     <p><strong>Message:</strong> ${submission.message || '(none)'}</p>
    //   `,
    // })
    // -------------------------------------------------------

    return new Response(
      JSON.stringify({ success: true, message: 'Your message has been received.' }),
      {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      },
    )
  } catch {
    return new Response(
      JSON.stringify({ success: false, errors: ['Invalid request. Please try again.'] }),
      {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      },
    )
  }
}
