import { useState, useMemo } from 'react'

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
import { geoPath, geoAlbersUsa } from 'd3-geo'
import { feature } from 'topojson-client'
import { MapPin, Instagram, Users } from 'lucide-react'
import usTopology from '../data/us-states-10m.json'
import './About.css'

const projection = geoAlbersUsa().scale(1050).translate([480, 300])
const pathGenerator = geoPath(projection)
const states = feature(usTopology, usTopology.objects.states).features

const chapters = [
  {
    id: 'hhi',
    name: 'Hilton Head Island, SC',
    presidents: 'Kevin G. and Santiago F.',
    instagram: null,
    coordinates: [-80.726, 32.216],
  },
  {
    id: 'nyhs',
    name: 'Northwest Yeshiva High School, WA',
    presidents: 'Levi S.',
    instagram: 'incentive.nyhs',
    coordinates: [-122.332, 47.658],
  },
  {
    id: 'stl',
    name: 'St. Louis, MO',
    presidents: 'Ridhima K.',
    instagram: 'incentive.stlouis',
    coordinates: [-90.199, 38.627],
  },
  {
    id: 'lhs',
    name: 'Lingonore High School, MD',
    presidents: 'Bhavya Y. and Rashmika P.',
    instagram: 'incentive.lhs',
    coordinates: [-77.349, 39.377],
  },
]

export default function AboutPage() {
  const [activeChapter, setActiveChapter] = useState(null)

  const markers = useMemo(() => {
    return chapters
      .map((ch) => ({ ...ch, pos: projection(ch.coordinates) }))
      .filter((ch) => ch.pos)
  }, [])

  return (
    <>
      {/* ── HERO ── */}
      <section className="about-hero section">
        <div className="container">
          <div className="about-hero-text">
            <div className="about-hero-shapes">
              <div className="about-shape about-shape--circle" />
              <div className="about-shape about-shape--triangle" />
              <div className="about-shape about-shape--square" />
            </div>
            <h1 className="about-hero-title">
              The <span className="about-quote-accent">&ldquo;</span>Incentive<span className="about-quote-accent">&rdquo;</span> behind in<span className="brand-highlight">cent</span>ive
            </h1>
            <blockquote className="about-hero-quote">
              <p>
                The financial preparedness of our nation's youth is essential to their
                well-being and of vital importance to our economic future.
              </p>
              <cite>— <a href="https://en.wikipedia.org/wiki/Ben_Bernanke" target="_blank" rel="noopener noreferrer" className="about-cite-link">Ben Bernanke</a></cite>
            </blockquote>
          </div>
        </div>
      </section>

      {/* ── MISSION ── */}
      <section className="about-mission section">
        <div className="container">
          <div className="about-section-label">
            Our <span className="hero-highlight">Mission<Squiggle className="hero-squiggle" /></span>
          </div>
          <h2 className="about-mission-headline">
            Giving students the tools to lead,<br />teach, and make change.
          </h2>
          <div className="about-mission-body">
            <p>
              incentive is a student-led non-profit that is changing the way financial
              literacy education is brought to the classroom. With extensive opportunities
              for high school students to take rigorous leadership positions within their
              community, incentive gives these student educators a platform to make
              lasting change in their community.
            </p>
            <p>
              Instead of obsolete, old, and tiring systems that don't give students what
              they need, incentive brings a spark of youth into financial education for
              everyone. Every high schooler who joins incentive walks away with more than
              community service hours. They develop the ability to communicate complex
              ideas clearly, lead a room with confidence, take initiative, and build
              something that has real impact in their community.
            </p>
            <p>
              But at the same time, the same students being taught financial literacy
              have the opportunity to return the gesture and keep the cycle going.
              incentive isn't just a "one-off" project, it's a movement of student
              leaders and educators ready to make that next step to ensure financial
              freedom for everyone. From budgeting basics to investing fundamentals, our
              tools are designed to make learning about money feel approachable and
              exciting.
            </p>
          </div>
        </div>
      </section>

      {/* ── TEAM ── */}
      <section className="about-team section">
        <div className="container">
          <div className="about-section-label">
            Our <span className="hero-highlight">Team<Squiggle className="hero-squiggle" /></span>
          </div>

          <div className="about-team-group about-team-group--founders">
            <h3>Co-Founders</h3>
            <div className="about-team-grid">
              <div className="about-person-card">
                <div className="about-person-photo">
                  <img src="/images/matthew-park.jpg" alt="Matthew Park" />
                </div>
                <h4>Matthew Park</h4>
                <p className="about-person-role">Co-Founder</p>
                <div className="about-person-socials">
                  <a href="https://www.instagram.com/mattyp.21/" target="_blank" rel="noopener noreferrer" className="about-social-btn" aria-label="Matthew Instagram">
                    <img src="/images/instagram-logo.svg" alt="Instagram" />
                  </a>
                  <a href="https://www.linkedin.com/in/matthew-park-11b036309/" target="_blank" rel="noopener noreferrer" className="about-social-btn" aria-label="Matthew LinkedIn">
                    <img src="/images/linkedin-logo.jpg" alt="LinkedIn" />
                  </a>
                </div>
              </div>
              <div className="about-person-card">
                <div className="about-person-photo">
                  <img src="/images/sathvik-vadlakunta.jpeg" alt="Sathvik Vadlakunta" />
                </div>
                <h4>Sathvik Vadlakunta</h4>
                <p className="about-person-role">Co-Founder</p>
                <div className="about-person-socials">
                  <a href="https://www.instagram.com/sathvik.vadlakunta/" target="_blank" rel="noopener noreferrer" className="about-social-btn" aria-label="Sathvik Instagram">
                    <img src="/images/instagram-logo.svg" alt="Instagram" />
                  </a>
                  <a href="https://www.linkedin.com/in/sathvik-vadlakunta-239b03379/" target="_blank" rel="noopener noreferrer" className="about-social-btn" aria-label="Sathvik LinkedIn">
                    <img src="/images/linkedin-logo.jpg" alt="LinkedIn" />
                  </a>
                </div>
              </div>
            </div>
          </div>

          <div className="about-team-group">
            <h3>Social Media</h3>
            <div className="about-team-grid">
              <div className="about-person-card">
                <div className="about-person-photo">
                  <img src="/images/esha-yarram.jpeg" alt="Esha Yarram" />
                </div>
                <h4>Esha Yarram</h4>
                <p className="about-person-role">Social Media Coordinator</p>
                <div className="about-person-socials">
                  <a href="https://www.instagram.com/eshayarram/" target="_blank" rel="noopener noreferrer" className="about-social-btn" aria-label="Esha Instagram">
                    <img src="/images/instagram-logo.svg" alt="Instagram" />
                  </a>
                </div>
              </div>
            </div>
          </div>

          <div className="about-team-group">
            <h3>Board of Advisors</h3>
            <div className="about-team-grid">
              <div className="about-person-card">
                <div className="about-person-photo">
                  <img src="/images/advisor.jpg" alt="Frederick Steinmann" />
                </div>
                <h4>Frederick Steinmann</h4>
                <p className="about-person-role">Assistant Research Professor at UNR</p>
                <div className="about-person-socials">
                  <a href="https://www.linkedin.com/in/fredsteinmann/" target="_blank" rel="noopener noreferrer" className="about-social-btn" aria-label="Frederick LinkedIn">
                    <img src="/images/linkedin-logo.jpg" alt="LinkedIn" />
                  </a>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── CHAPTERS ── */}
      <section className="about-chapters section">
        <div className="container">
          <div className="about-section-label">
            Our <span className="hero-highlight">Chapters<Squiggle className="hero-squiggle" /></span>
          </div>
          <p className="about-chapters-sub">
            Click a pin on the map to learn more about each chapter.
          </p>

          <div className="about-map-card">
            <svg
              viewBox="0 0 960 600"
              className="about-map-svg"
              onClick={() => setActiveChapter(null)}
            >
              {states.map((state, i) => (
                <path key={i} d={pathGenerator(state)} className="about-map-state" />
              ))}
              {markers.map((ch) => (
                <g key={ch.id} className="about-map-marker-group">
                  <circle cx={ch.pos[0]} cy={ch.pos[1]} r={14} className="about-map-pin-ring" />
                  <circle
                    cx={ch.pos[0]}
                    cy={ch.pos[1]}
                    r={8}
                    className={`about-map-pin ${activeChapter?.id === ch.id ? 'about-map-pin--active' : ''}`}
                    onClick={(e) => {
                      e.stopPropagation()
                      setActiveChapter(activeChapter?.id === ch.id ? null : ch)
                    }}
                  />
                </g>
              ))}
            </svg>

            {activeChapter && (
              <div className="about-chapter-popup" onClick={(e) => e.stopPropagation()}>
                <button className="about-chapter-close" onClick={() => setActiveChapter(null)} aria-label="Close">
                  &times;
                </button>
                <div className="about-chapter-header">
                  <MapPin size={18} strokeWidth={2.5} />
                  <h4>{activeChapter.name}</h4>
                </div>
                <div className="about-chapter-detail">
                  <Users size={16} strokeWidth={2} />
                  <span>{activeChapter.presidents}</span>
                </div>
                {activeChapter.instagram ? (
                  <a href={`https://instagram.com/${activeChapter.instagram}`} target="_blank" rel="noopener noreferrer" className="about-chapter-ig">
                    <Instagram size={16} strokeWidth={2} />
                    @{activeChapter.instagram}
                  </a>
                ) : (
                  <div className="about-chapter-detail about-chapter-detail--muted">
                    <Instagram size={16} strokeWidth={2} />
                    <span>N/A</span>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </section>
    </>
  )
}
