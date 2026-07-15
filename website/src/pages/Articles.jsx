import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { fetchArticles } from '../lib/articlesApi'
import { Calendar, User } from 'lucide-react'
import './Articles.css'

function formatDate(iso) {
  return new Date(iso).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
}

function excerpt(body, max = 180) {
  if (!body) return ''
  return body.length > max ? body.slice(0, max).trimEnd() + '…' : body
}

export default function ArticlesPage() {
  const [articles, setArticles] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState('')

  useEffect(() => {
    fetchArticles()
      .then(setArticles)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  return (
    <main>
      <section className="articles-hero section">
        <div className="container">
          <h1 className="articles-title">
            in<span className="brand-highlight">cent</span>ive Articles
          </h1>
          <p className="articles-subtitle">
            Financial literacy insights, tips, and stories from our team.
          </p>
        </div>
      </section>

      <section className="articles-list section">
        <div className="container">
          {loading && <p className="articles-empty">Loading articles…</p>}
          {error   && <p className="articles-empty">Failed to load articles.</p>}
          {!loading && !error && articles.length === 0 && (
            <p className="articles-empty">No articles yet — check back soon.</p>
          )}
          <div className="articles-grid">
            {articles.map(a => (
              <Link key={a.id} to={`/articles/${a.id}`} className="article-card">
                <div className="article-card-body">
                  <h2 className="article-card-title">{a.title}</h2>
                  <p className="article-card-excerpt">{excerpt(a.body)}</p>
                </div>
                <div className="article-card-meta">
                  {a.author && (
                    <span className="article-meta-item">
                      <User size={13} strokeWidth={2} />
                      {a.author}
                    </span>
                  )}
                  <span className="article-meta-item">
                    <Calendar size={13} strokeWidth={2} />
                    {formatDate(a.published_at)}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </section>
    </main>
  )
}
