// Which accounts are allowed into /admin. Configurable via env so you can add
// more editors later without touching code — comma-separated list.
// Falls back to the owner's email if the env var isn't set.
const configured = import.meta.env.VITE_ADMIN_EMAILS
const ADMIN_EMAILS = (configured ? configured.split(',') : ['incentivefinanceinfo@gmail.com'])
  .map(e => e.trim().toLowerCase())
  .filter(Boolean)

export function isAdmin(user) {
  if (!user?.email) return false
  return ADMIN_EMAILS.includes(user.email.toLowerCase())
}
