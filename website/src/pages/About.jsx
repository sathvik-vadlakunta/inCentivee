import { useState } from 'react'
import { ComposableMap, Geographies, Geography, Marker } from 'react-simple-maps'
import { MapPin, Instagram, Users } from 'lucide-react'
import './About.css'

const GEO_URL = 'https://cdn.jsdelivr.net/npm/us-atlas@3/states-10m.json'

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

  return (
    <>
      <section className="about-hero section">
        <div className="container">
          <div className="about-hero-shapes">
            <div className="about-shape about-shape--circle" />
            <div className="about-shape about-shape--triangle" />
            <div className="about-shape about-shape--square" />
          </div>
          <h1>About InCentive</h1>
          <p className="about-hero-sub">
            Empowering the next generation with financial confidence.
          </p>
        </div>
      </section>

      <section className="about-mission section">
        <div className="container">
          <div className="about-mission-content">
            <h2>Our Mission</h2>
            <p>
              InCentive is a student-led organization on a mission to make financial
              literacy accessible, engaging, and fun for everyone.
            </p>
            <p>
              We believe that understanding money is one of the most important life
              skills you can develop. But too often, financial education is either
              missing from classrooms or taught in ways that feel disconnected from
              real life. That is why we built InCentive.
            </p>
            <p>
              Through interactive presentations, hands-on calculators, and a growing
              network of chapters across the United States, we bring financial education
              directly to students and communities. From budgeting basics to investing
              fundamentals, our tools are designed to make learning about money feel
              approachable and exciting.
            </p>
            <p>
              What started as a passion project by two students has grown into a
              movement with chapters spanning from coast to coast. InCentive is proof
              that young people can lead meaningful change in their communities.
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
              </div>
              <div className="about-person-card">
                <div className="about-person-photo">
                  <img src="/images/sathvik-vadlakunta.jpeg" alt="Sathvik Vadlakunta" />
                </div>
                <h4>Sathvik Vadlakunta</h4>
                <p className="about-person-role">Co-Founder</p>
              </div>
            </div>
          </div>

          <div className="about-team-group">
            <h3>Board of Advisors</h3>
            <div className="about-team-grid">
              <div className="about-person-card">
                <div className="about-person-photo">
                  <img src="/images/advisor.jpg" alt="Board Advisor" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="about-chapters section">
        <div className="container">
          <h2>Our Chapters</h2>
          <p className="about-chapters-sub">
            Click a pin on the map to learn more about each chapter.
          </p>

          <div
            className="about-map-wrapper"
            onClick={() => setActiveChapter(null)}
          >
            <ComposableMap
              projection="geoAlbersUsa"
              width={800}
              height={500}
              className="about-map"
            >
              <Geographies geography={GEO_URL}>
                {({ geographies }) =>
                  geographies.map((geo) => (
                    <Geography
                      key={geo.rsmKey}
                      geography={geo}
                      className="about-map-state"
                      tabIndex={-1}
                    />
                  ))
                }
              </Geographies>
              {chapters.map((ch) => (
                <Marker key={ch.id} coordinates={ch.coordinates}>
                  <circle r={12} className="about-map-pin-pulse" />
                  <circle
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
                </Marker>
              ))}
            </ComposableMap>

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
