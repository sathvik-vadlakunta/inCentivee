import { useState } from 'react'
import { Menu, X, ArrowRight } from 'lucide-react'
import Button from './Button'
import './Navbar.css'

const links = [
  { label: 'Programs', href: '#programs' },
  { label: 'About', href: '#about' },
  { label: 'Community', href: '#community' },
]

export default function Navbar() {
  const [open, setOpen] = useState(false)

  return (
    <header className="navbar">
      <nav className="navbar-inner container">
        <a href="/" className="navbar-brand" aria-label="InCentive home">
          <span className="brand-dot" />
          InCentive
        </a>

        <ul className={`navbar-links ${open ? 'navbar-links--open' : ''}`}>
          {links.map(({ label, href }) => (
            <li key={href}>
              <a href={href} onClick={() => setOpen(false)}>{label}</a>
            </li>
          ))}
        </ul>

        <div className="navbar-actions">
          <Button variant="primary" icon={ArrowRight} href="#cta">
            Get Started
          </Button>
        </div>

        <button
          className="navbar-toggle"
          aria-label={open ? 'Close menu' : 'Open menu'}
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? <X size={24} strokeWidth={2.5} /> : <Menu size={24} strokeWidth={2.5} />}
        </button>
      </nav>

      {open && (
        <div className="navbar-mobile">
          <ul>
            {links.map(({ label, href }) => (
              <li key={href}>
                <a href={href} onClick={() => setOpen(false)}>{label}</a>
              </li>
            ))}
          </ul>
          <Button variant="primary" icon={ArrowRight} href="#cta" onClick={() => setOpen(false)}>
            Get Started
          </Button>
        </div>
      )}
    </header>
  )
}
