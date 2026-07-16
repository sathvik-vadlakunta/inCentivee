import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Zap, Plus, Trash2, Copy, Check, Pencil } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { fetchMyQuizzes, deleteQuiz } from '../lib/quizzesApi'
import Button from '../components/Button'
import './Quizzes.css'

export default function QuizzesPage() {
  const [code, setCode]       = useState('')
  const [error, setError]     = useState('')
  const [myQuizzes, setMyQuizzes] = useState([])
  const [copied, setCopied]   = useState(null)
  const { currentUser }       = useAuth()
  const navigate              = useNavigate()

  useEffect(() => {
    if (!currentUser) return
    fetchMyQuizzes(currentUser.id).then(setMyQuizzes).catch(() => {})
  }, [currentUser])

  function handleJoin(e) {
    e.preventDefault()
    const trimmed = code.trim().toUpperCase()
    if (!trimmed) { setError('Enter a quiz code.'); return }
    navigate(`/quizzes/${trimmed}`)
  }

  async function handleDelete(quiz) {
    if (!window.confirm(`Delete "${quiz.title}"?`)) return
    await deleteQuiz(quiz.id)
    setMyQuizzes(prev => prev.filter(q => q.id !== quiz.id))
  }

  function copyCode(code) {
    navigator.clipboard.writeText(code)
    setCopied(code)
    setTimeout(() => setCopied(null), 2000)
  }

  return (
    <section className="quiz-page section">
      <div className="container">
        <div className="quiz-hero">
          <div className="pres-shape pres-shape--circle" />
          <div className="pres-shape pres-shape--triangle" />
          <div className="pres-shape pres-shape--square" />
          <div className="pres-icon-badge">
            <Zap size={28} strokeWidth={2.5} />
          </div>
          <h1>Join a Quiz</h1>
          <p className="pres-subtitle">
            Enter the code shared by your quiz creator to start.
          </p>
        </div>

        <form className="pres-join-card" onSubmit={handleJoin}>
          <label className="pres-label" htmlFor="quiz-code">Quiz Code</label>
          <input
            id="quiz-code"
            className={`pres-code-input${error ? ' pres-code-input--error' : ''}`}
            type="text"
            placeholder="ENTER CODE"
            value={code}
            onChange={e => { setCode(e.target.value.toUpperCase()); setError('') }}
            maxLength={6}
            autoComplete="off"
          />
          {error && <p className="pres-error">{error}</p>}
          <Button variant="primary" icon={Zap}>Join Quiz</Button>
        </form>

        <div className="quiz-divider">
          <span>or</span>
        </div>

        {currentUser ? (
          <div className="quiz-create-section">
            <Link to="/quizzes/create" className="btn btn-secondary quiz-create-btn">
              <Plus size={18} strokeWidth={2.5} />
              <span>Create your own quiz</span>
            </Link>

            {myQuizzes.length > 0 && (
              <div className="quiz-my-list">
                <p className="quiz-my-label">Your quizzes</p>
                {myQuizzes.map(q => (
                  <div key={q.id} className="quiz-my-card">
                    <div className="quiz-my-info">
                      <span className="quiz-my-title">{q.title}</span>
                      <button className="quiz-code-chip" onClick={() => copyCode(q.code)} title="Copy code">
                        {copied === q.code ? <Check size={12} /> : <Copy size={12} />}
                        {q.code}
                      </button>
                    </div>
                    <div className="quiz-my-actions">
                      <Link to={`/quizzes/edit/${q.id}`} className="quiz-icon-btn" title="Edit">
                        <Pencil size={15} />
                      </Link>
                      <button className="quiz-icon-btn quiz-icon-btn--danger" onClick={() => handleDelete(q)} title="Delete">
                        <Trash2 size={15} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="quiz-create-section quiz-create-section--guest">
            <p className="quiz-guest-text">
              <Link to="/login" className="quiz-guest-link">Log in</Link> to create and share your own quizzes.
            </p>
          </div>
        )}
      </div>
    </section>
  )
}
