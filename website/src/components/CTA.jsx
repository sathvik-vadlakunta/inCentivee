import { ArrowRight, BookOpen } from 'lucide-react'
import { Link } from 'react-router-dom'
import Button from './Button'
import './CTA.css'

export default function CTA() {
  return (
    <section className="cta section" id="cta">
      <div className="cta-confetti" aria-hidden="true">
        <span className="confetti confetti--circle confetti--1" />
        <span className="confetti confetti--triangle confetti--2" />
        <span className="confetti confetti--square confetti--3" />
        <span className="confetti confetti--circle confetti--4" />
        <span className="confetti confetti--triangle confetti--5" />
        <span className="confetti confetti--square confetti--6" />
      </div>

      <div className="cta-inner container">
        {/* Left column — volunteer */}
        <div className="cta-col">
          <p className="cta-eyebrow">Get Involved</p>
          <h2 className="cta-title">
            Want to help us make a&nbsp;difference?
          </h2>
          <p className="cta-subtitle">
            Join our mission to equip people with the financial knowledge they
            deserve. Volunteer in your local schools, libraries, and community
            spaces to help break down barriers around money.
          </p>
          <Button
            variant="primary"
            icon={ArrowRight}
            href="https://docs.google.com/forms/d/e/1FAIpQLScgWDzXExB0Xe86eI70V7-96cIr-A_0bcAXC41dGyyRl8JdXA/viewform?usp=dialog"
            target="_blank"
            rel="noopener noreferrer"
            className="cta-btn"
          >
            Volunteer Today
          </Button>
        </div>

        <div className="cta-divider" aria-hidden="true" />

        {/* Right column — learn */}
        <div className="cta-col">
          <p className="cta-eyebrow">Start Learning</p>
          <h2 className="cta-title">
            Want to start learning today?
          </h2>
          <p className="cta-subtitle">
            Dive into bite-sized financial literacy lessons, earn cents for
            every quiz you complete, and build real money skills at your own
            pace — completely free.
          </p>
          <div className="cta-learn-actions">
            <Link to="/learn" className="btn btn-primary cta-btn">
              <span className="btn-label">Explore Lessons</span>
              <span className="btn-icon-badge"><BookOpen size={18} strokeWidth={2.5} /></span>
            </Link>
            <Link to="/login" className="btn btn-secondary cta-btn-secondary">
              <span className="btn-label">Log in</span>
              <span className="btn-icon-badge"><ArrowRight size={18} strokeWidth={2.5} /></span>
            </Link>
          </div>
        </div>
      </div>
    </section>
  )
}
