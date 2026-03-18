import { ArrowRight, Play } from 'lucide-react'
import Button from './Button'
import './Hero.css'

function Squiggle({ className }) {
  return (
    <svg className={className} viewBox="0 0 200 12" fill="none" preserveAspectRatio="none">
      <path
        d="M2 8 C 20 2, 40 12, 60 6 S 100 2, 120 8 S 160 12, 180 6 S 198 4, 198 4"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
        fill="none"
      />
    </svg>
  )
}

export default function Hero() {
  return (
    <section className="hero section" id="about">
      <div className="hero-inner container">
        <div className="hero-content">
          <div className="hero-badge">
            <span className="hero-badge-dot" />
            Financial Education for Everyone
          </div>

          <h1 className="hero-title">
            Learn Money.
            <br />
            Build{' '}
            <span className="hero-highlight">
              Confidence
              <Squiggle className="hero-squiggle" />
            </span>
            .
          </h1>

          <p className="hero-subtitle">
            incentive makes personal finance approachable, interactive,
            and actually fun. Build real skills with courses designed for
            the way you learn.
          </p>

          <div className="hero-actions">
            <Button variant="primary" icon={ArrowRight} href="#cta">
              Start Learning Free
            </Button>
            <Button variant="secondary" icon={Play} href="#programs">
              See Programs
            </Button>
          </div>

          <div className="hero-proof">
            <div className="hero-avatars">
              <div className="hero-avatar" style={{ background: 'var(--secondary)' }}>J</div>
              <div className="hero-avatar" style={{ background: 'var(--tertiary)' }}>A</div>
              <div className="hero-avatar" style={{ background: 'var(--quaternary)' }}>M</div>
              <div className="hero-avatar" style={{ background: 'var(--accent)' }}>S</div>
            </div>
            <p className="hero-proof-text">
              <strong>2,400+</strong> learners already growing their financial confidence
            </p>
          </div>
        </div>

        <div className="hero-visual" aria-hidden="true">
          <div className="hero-shape hero-shape--circle" />
          <div className="hero-shape hero-shape--dots" />
          <div className="hero-shape hero-shape--triangle" />
          <div className="hero-shape hero-shape--pill" />
          <div className="hero-shape hero-shape--square" />
        </div>
      </div>
    </section>
  )
}
