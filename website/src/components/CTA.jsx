import { ArrowRight } from 'lucide-react'
import Button from './Button'
import './CTA.css'

export default function CTA() {
  return (
    <section className="cta section" id="cta">
      {/* Confetti shapes */}
      <div className="cta-confetti" aria-hidden="true">
        <span className="confetti confetti--circle confetti--1" />
        <span className="confetti confetti--triangle confetti--2" />
        <span className="confetti confetti--square confetti--3" />
        <span className="confetti confetti--circle confetti--4" />
        <span className="confetti confetti--triangle confetti--5" />
        <span className="confetti confetti--square confetti--6" />
      </div>

      <div className="cta-inner container">
        <h2 className="cta-title">
          Start Your Financial Journey&nbsp;Today
        </h2>
        <p className="cta-subtitle">
          No credit card required. Jump in with free courses and join a
          community of people taking control of their money.
        </p>
        <Button
          variant="primary"
          icon={ArrowRight}
          href="#"
          className="cta-btn"
        >
          Create Free Account
        </Button>
      </div>
    </section>
  )
}
