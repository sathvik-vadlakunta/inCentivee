import { useState, useMemo } from 'react'
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
      <section className="about-hero section">
        <div className="container">
          <div className="about-hero-shapes">
            <div className="about-shape about-shape--circle" />
            <div className="about-shape about-shape--triangle" />
            <div className="about-shape about-shape--square" />
          </div>
          <h1>About in<span className="brand-highlight">cent</span>ive</h1>
          <p className="about-hero-sub">
            Empowering the next generation with financial confidence.
          </p>
        </div>
      </section>

      <div className="about-split">
      <section className="about-mission section">
        <div className="container">
          <div className="about-mission-content">
            <h2>Our Mission</h2>
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

      <section className="about-team section">
        <div className="container">
          <h2>Our Team</h2>

          <div className="about-team-group">
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
            <h3>Board of Advisors</h3>
            <div className="about-team-grid">
              <div className="about-person-card">
                <div className="about-person-photo">
                  <img src="/images/advisor.jpg" alt="Frederick Steinmann" />
                </div>
                <h4>Frederick Steinmann</h4>
                <p className="about-person-role">
                  Assistant Research Professor at UNR
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      </div>

      <section className="about-chapters section">
        <div className="container">
          <h2>Our Chapters</h2>
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
                <path
                  key={i}
                  d={pathGenerator(state)}
                  className="about-map-state"
                />
              ))}
              {markers.map((ch) => (
                <g key={ch.id} className="about-map-marker-group">
                  <circle
                    cx={ch.pos[0]}
                    cy={ch.pos[1]}
                    r={14}
                    className="about-map-pin-ring"
                  />
                  <circle
                    cx={ch.pos[0]}
                    cy={ch.pos[1]}
                    r={8}
                    className={`about-map-pin ${
                      activeChapter?.id === ch.id ? 'about-map-pin--active' : ''
                    }`}
                    onClick={(e) => {
                      e.stopPropagation()
                      setActiveChapter(
                        activeChapter?.id === ch.id ? null : ch
                      )
                    }}
                  />
                </g>
              ))}
            </svg>

            {activeChapter && (
              <div
                className="about-chapter-popup"
                onClick={(e) => e.stopPropagation()}
              >
                <button
                  className="about-chapter-close"
                  onClick={() => setActiveChapter(null)}
                  aria-label="Close"
                >
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
                  <a
                    href={`https://instagram.com/${activeChapter.instagram}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="about-chapter-ig"
                  >
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
