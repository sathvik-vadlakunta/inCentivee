import { Instagram, Twitter, Youtube, Mail } from 'lucide-react'
import './Footer.css'

const linkGroups = [
  {
    heading: 'Programs',
    links: [
      { label: 'Budgeting 101', href: '#' },
      { label: 'Investing Basics', href: '#' },
      { label: 'Credit & Debt', href: '#' },
      { label: 'Saving Strategies', href: '#' },
    ],
  },
  {
    heading: 'Company',
    links: [
      { label: 'About Us', href: '#' },
      { label: 'Our Team', href: '#' },
      { label: 'Careers', href: '#' },
      { label: 'Contact', href: '#' },
    ],
  },
  {
    heading: 'Resources',
    links: [
      { label: 'Blog', href: '#' },
      { label: 'Newsletter', href: '#' },
      { label: 'Help Center', href: '#' },
      { label: 'Privacy Policy', href: '#' },
    ],
  },
]

const socials = [
  { icon: Instagram, href: '#', label: 'Instagram' },
  { icon: Twitter, href: '#', label: 'Twitter' },
  { icon: Youtube, href: '#', label: 'YouTube' },
  { icon: Mail, href: '#', label: 'Email' },
]

export default function Footer() {
  return (
    <footer className="footer">
      <div className="footer-inner container">
        <div className="footer-brand">
          <a href="/" className="footer-logo" aria-label="InCentive home">
            <span className="footer-logo-dot" />
            InCentive
          </a>
          <p className="footer-tagline">
            Making financial literacy accessible, engaging, and fun for everyone.
          </p>
          <div className="footer-socials">
            {socials.map((social) => {
              const SocialIcon = social.icon
              return (
                <a
                  key={social.label}
                  href={social.href}
                  className="footer-social-link"
                  aria-label={social.label}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <SocialIcon size={18} strokeWidth={2.5} />
                </a>
              )
            })}
          </div>
        </div>

        {linkGroups.map((group) => (
          <div className="footer-group" key={group.heading}>
            <h4 className="footer-group-heading">{group.heading}</h4>
            <ul>
              {group.links.map((link) => (
                <li key={link.label}>
                  <a href={link.href}>{link.label}</a>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <div className="footer-bottom container">
        <p>&copy; {new Date().getFullYear()} InCentive. All rights reserved.</p>
      </div>
    </footer>
  )
}
