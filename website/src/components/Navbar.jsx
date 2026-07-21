import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Menu, X, LogIn, LogOut, Zap } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import './Navbar.css'

const links = [
  { label: 'Learn', href: '/learn' },
  { label: 'Resources', href: '/resources' },
  { label: 'Articles', href: '/articles' },
  { label: 'Quizzes', href: '/quizzes' },
  { label: 'About', href: '/about' },
]

export default function Navbar() {
  const [open, setOpen] = useState(false)
  const { currentUser, profile, logOut } = useAuth()
  const navigate = useNavigate()

  const coins = profile?.xp ?? 0
  const xp    = coins * 2

  async function handleLogOut() {
    await logOut()
    navigate('/')
    setOpen(false)
  }

  return (
    <header className="navbar">
      <nav className="navbar-inner container">
        <Link to="/" className="navbar-brand" aria-label="incentive home">
          <img src="/coin-logo.png" alt="" className="navbar-brand-logo" />
          <span>in<span className="brand-highlight">cent</span>ive</span>
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
              <div className="navbar-xp" data-tooltip="This is your XP, you earn it every time you complete a lesson">
                <Zap size={14} strokeWidth={2.5} className="navbar-xp-icon" />
                <span className="navbar-xp-count">{xp}</span>
              </div>
              <div className="navbar-cents" data-tooltip="This is how many cents you've earned">
                <span className="navbar-cents-coin">¢</span>
                <span className="navbar-cents-count">{coins}</span>
              </div>
              <button className="btn btn-secondary navbar-logout" onClick={handleLogOut}>
                <span className="btn-label">Log out</span>
                <span className="btn-icon-badge"><LogOut size={16} strokeWidth={2.5} /></span>
              </button>
            </>
          ) : (
            <>
              <div className="navbar-xp navbar-xp--guest" data-tooltip="Log in to start earning XP">
                <Zap size={14} strokeWidth={2.5} className="navbar-xp-icon" />
                <span className="navbar-xp-count">0</span>
              </div>
              <div className="navbar-cents navbar-cents--guest" data-tooltip="Log in to start earning cents">
                <span className="navbar-cents-coin">¢</span>
                <span className="navbar-cents-count">0</span>
              </div>
              <button className="btn btn-secondary navbar-logout" onClick={() => navigate('/login')}>
                <span className="btn-label">Log in</span>
                <span className="btn-icon-badge"><LogIn size={16} strokeWidth={2.5} /></span>
              </button>
            </>
          )}
        </div>

        <div className="navbar-end">
          <div className={`navbar-xp navbar-xp--mobile${!currentUser ? ' navbar-xp--guest' : ''}`} title="Your XP" aria-hidden="true">
            <Zap size={12} strokeWidth={2.5} className="navbar-xp-icon" />
            <span className="navbar-xp-count">{currentUser ? xp : 0}</span>
          </div>
          <div className={`navbar-cents navbar-cents--mobile${!currentUser ? ' navbar-cents--guest' : ''}`} title="Your cents" aria-hidden="true">
            <span className="navbar-cents-coin">¢</span>
            <span className="navbar-cents-count">{currentUser ? coins : 0}</span>
          </div>
          {!currentUser && (
            <button className="btn btn-secondary navbar-mobile-login" onClick={() => navigate('/login')}>
              <span className="btn-label">Log in</span>
              <span className="btn-icon-badge"><LogIn size={16} strokeWidth={2.5} /></span>
            </button>
          )}
          <button
            className="navbar-toggle"
            aria-label={open ? 'Close menu' : 'Open menu'}
            aria-expanded={open}
            onClick={() => setOpen(v => !v)}
          >
            {open ? <X size={24} strokeWidth={2.5} /> : <Menu size={24} strokeWidth={2.5} />}
          </button>
        </div>
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
              <div className="navbar-xp">
                <Zap size={14} strokeWidth={2.5} className="navbar-xp-icon" />
                <span className="navbar-xp-count">{xp}</span>
              </div>
              <div className="navbar-cents">
                <span className="navbar-cents-coin">¢</span>
                <span className="navbar-cents-count">{coins}</span>
              </div>
              <button className="btn btn-secondary" onClick={handleLogOut} style={{ flex: 1, justifyContent: 'center' }}>
                <span className="btn-label">Log out</span>
                <span className="btn-icon-badge"><LogOut size={16} strokeWidth={2.5} /></span>
              </button>
            </div>
          ) : (
            <button className="btn btn-secondary" onClick={() => { navigate('/login'); setOpen(false) }} style={{ alignSelf: 'stretch', justifyContent: 'center' }}>
              <span className="btn-label">Log in</span>
              <span className="btn-icon-badge"><LogIn size={16} strokeWidth={2.5} /></span>
            </button>
          )}
        </div>
      )}
    </header>
  )
}
