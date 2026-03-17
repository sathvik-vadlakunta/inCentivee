import { BookOpen, Users, TrendingUp } from 'lucide-react'
import Card from './Card'
import './Features.css'

const features = [
  {
    icon: BookOpen,
    color: 'secondary',
    title: 'Interactive Courses',
    body: 'Bite-sized lessons on budgeting, saving, investing, and credit — built for real life, not textbooks.',
  },
  {
    icon: Users,
    color: 'accent',
    title: 'Community Support',
    body: 'Learn alongside peers, share wins, ask questions, and stay motivated with group accountability.',
  },
  {
    icon: TrendingUp,
    color: 'tertiary',
    title: 'Real-World Tools',
    body: 'Budget planners, savings trackers, and investment simulators that put theory into practice.',
  },
]

export default function Features() {
  return (
    <section className="features section" id="programs">
      <div className="features-inner container">
        <div className="features-header">
          <h2 className="features-title">
            Everything you need to{' '}
            <span className="features-highlight">level up</span>
          </h2>
          <p className="features-subtitle">
            Programs designed to meet you where you are and take you where you want to go.
          </p>
        </div>

        <div className="features-grid">
          {/* Dashed connector line behind cards */}
          <svg className="features-connector" aria-hidden="true" preserveAspectRatio="none">
            <line
              x1="16.5%"
              y1="50%"
              x2="83.5%"
              y2="50%"
              stroke="var(--border)"
              strokeWidth="2"
              strokeDasharray="8 6"
            />
          </svg>

          {features.map((f) => (
            <Card
              key={f.title}
              icon={f.icon}
              color={f.color}
              title={f.title}
            >
              {f.body}
            </Card>
          ))}
        </div>
      </div>
    </section>
  )
}
