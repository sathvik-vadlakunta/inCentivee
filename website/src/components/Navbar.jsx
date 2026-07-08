import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Menu, X, ArrowRight, LogOut } from 'lucide-react'
import Button from './Button'
import { useAuth } from '../context/AuthContext'
import './Navbar.css'

const links = [
  { label: 'Learn', href: '/learn' },
  { label: 'Resources', href: '/resources' },
  { label: 'Presentations', href: '/presentations' },
  { label: 'About', href: '/about' },
]

export default function Navbar() {
  const [open, setOpen] = useState(false)
  const { currentUser, profile, logOut } = useAuth()
  const navigate = useNavigate()

  async function handleLogOut() {
    await logOut()
    navigate('/')
    setOpen(false)
  }

  return (
    <header className="navbar">
      <nav className="navbar-inner container">
        <Link to="/" className="navbar-brand" aria-label="incentive home">
          in<span className="brand-highlight">cent</span>ive
        </Link>

        <ul className={`navbar-links ${open ? 'navbar-links--open' : ''}`}>
          {links.map(({ label, href }) => (
            <li key={href}>
              <Link to={href} onClick={() => setOpen(false)}>{label}</Link>
            </li>
          ))}
        </ul>

        <div className="navbar-actions">
          {currentUser ? (
            <>
              <div className="navbar-cents" title="Your cents">
                <span className="navbar-cents-coin">¢</span>
                <span className="navbar-cents-count">{profile?.xp ?? 0}</span>
              </div>
              <button className="btn btn-secondary navbar-logout" onClick={handleLogOut}>
                <span className="btn-label">Log out</span>
                <span className="btn-icon-badge"><LogOut size={16} strokeWidth={2.5} /></span>
              </button>
            </>
          ) : (
            <>
              <div className="navbar-cents navbar-cents--guest" title="Log in to earn cents">
                <span className="navbar-cents-coin">¢</span>
                <span className="navbar-cents-count">0</span>
              </div>
              <Button variant="primary" icon={ArrowRight} href="/#cta">
                Get Started
              </Button>
            </>
          )}
        </div>

        <button
          className="navbar-toggle"
          aria-label={open ? 'Close menu' : 'Open menu'}
          aria-expanded={open}
          onClick={() => setOpen(v => !v)}
        >
          {open ? <X size={24} strokeWidth={2.5} /> : <Menu size={24} strokeWidth={2.5} />}
        </button>
      </nav>

      {open && (
        <div className="navbar-mobile">
          <ul>
            {links.map(({ label, href }) => (
              <li key={href}>
                <Link to={href} onClick={() => setOpen(false)}>{label}</Link>
              </li>
            ))}
          </ul>
          {currentUser ? (
            <div className="navbar-mobile-bottom">
              <div className="navbar-cents">
                <span className="navbar-cents-coin">¢</span>
                <span className="navbar-cents-count">{profile?.xp ?? 0}</span>
              </div>
              <button className="btn btn-secondary" onClick={handleLogOut} style={{ flex: 1, justifyContent: 'center' }}>
                <span className="btn-label">Log out</span>
                <span className="btn-icon-badge"><LogOut size={16} strokeWidth={2.5} /></span>
              </button>
            </div>
          ) : (
            <Button variant="primary" icon={ArrowRight} href="/#cta" onClick={() => setOpen(false)}>
              Get Started
            </Button>
          )}
        </div>
      )}
    </header>
  )
}
