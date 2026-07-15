import { useState, useEffect } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'
import { fetchArticle } from '../lib/articlesApi'
import { ArrowLeft, Calendar, User } from 'lucide-react'
import './Articles.css'

function formatDate(iso) {
  return new Date(iso).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
}

export default function ArticlePage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [article, setArticle] = useState(null)
  const [error, setError]     = useState('')

  useEffect(() => {
    fetchArticle(id)
      .then(setArticle)
      .catch(() => setError('Article not found.'))
  }, [id])

  if (error) return (
    <main>
      <section className="section">
        <div className="container article-page">
          <p>{error}</p>
          <Link to="/articles" className="article-back"><ArrowLeft size={14} /> Back to Articles</Link>
        </div>
      </section>
    </main>
  )

  if (!article) return (
    <main>
      <section className="section">
        <div className="container article-page">
          <p style={{ color: 'var(--muted-foreground)' }}>Loading…</p>
        </div>
      </section>
    </main>
  )

  return (
    <main>
      <section className="section">
        <div className="container article-page">
          <Link to="/articles" className="article-back">
            <ArrowLeft size={14} /> Back to Articles
          </Link>
          <h1 className="article-heading">{article.title}</h1>
          <div className="article-meta">
            {article.author && (
              <span className="article-meta-item">
                <User size={14} strokeWidth={2} />
                {article.author}
              </span>
            )}
            <span className="article-meta-item">
              <Calendar size={14} strokeWidth={2} />
              {formatDate(article.published_at)}
            </span>
          </div>
          <div className="article-body">{article.body}</div>
        </div>
      </section>
    </main>
  )
}
