import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, CheckCircle, XCircle, Trophy } from 'lucide-react'
import { fetchQuizByCode } from '../lib/quizzesApi'
import Button from '../components/Button'
import './Quizzes.css'
import './Presentations.css'

const COLORS = ['var(--accent)', 'var(--quaternary)', 'var(--tertiary)', 'var(--secondary)']
const LETTERS = ['A', 'B', 'C', 'D']

function fisherYates(arr) {
  const a = [...arr]
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[a[i], a[j]] = [a[j], a[i]]
  }
  return a
}

function shuffleQuestion(q) {
  const correct = q.options[q.correct]
  const opts    = fisherYates(q.options)
  return { ...q, options: opts, correct: opts.indexOf(correct) }
}

export default function QuizTaker() {
  const { code }                    = useParams()
  const [quiz, setQuiz]             = useState(null)
  const [questions, setQuestions]   = useState([])
  const [error, setError]           = useState('')
  const [qIndex, setQIndex]         = useState(0)
  const [selected, setSelected]     = useState(null)
  const [showFeedback, setShowFeedback] = useState(false)
  const [score, setScore]           = useState(0)
  const [done, setDone]             = useState(false)

  useEffect(() => {
    fetchQuizByCode(code)
      .then(data => {
        setQuiz(data)
        setQuestions(data.quiz_questions.map(shuffleQuestion))
      })
      .catch(() => setError('Quiz not found. Check your code and try again.'))
  }, [code])

  if (error) return (
    <section className="section">
      <div className="container pv-not-found">
        <h2>Quiz not found</h2>
        <p>{error}</p>
        <Link to="/quizzes" className="pv-not-found-link"><ArrowLeft size={16} /> Back to Quizzes</Link>
      </div>
    </section>
  )

  if (!quiz) return (
    <section className="section">
      <div className="container" style={{ textAlign: 'center', color: 'var(--muted-foreground)' }}>
        Loading quiz…
      </div>
    </section>
  )

  if (questions.length === 0) return (
    <section className="section">
      <div className="container pv-not-found">
        <h2>{quiz.title}</h2>
        <p>This quiz has no questions yet.</p>
        <Link to="/quizzes" className="pv-not-found-link"><ArrowLeft size={16} /> Back to Quizzes</Link>
      </div>
    </section>
  )

  if (done) {
    const pct = Math.round((score / questions.length) * 100)
    return (
      <section className="section">
        <div className="container quiz-taker">
          <div className="pv-results">
            <div className="pv-results-icon"><Trophy size={48} strokeWidth={2} /></div>
            <h2>Quiz Complete!</h2>
            <div className="pv-score-display">
              <span className="pv-score-number">{score}</span>
              <span className="pv-score-max"> / {questions.length}</span>
            </div>
            <p className="pv-rank" style={{ color: pct >= 80 ? 'var(--tertiary)' : pct >= 50 ? 'var(--secondary)' : 'var(--accent)' }}>
              {pct >= 80 ? 'Excellent!' : pct >= 50 ? 'Good effort!' : 'Keep studying!'}
            </p>
            <div className="pv-stats">
              <div className="pv-stat"><span className="pv-stat-value">{score}</span><span className="pv-stat-label">Correct</span></div>
              <div className="pv-stat"><span className="pv-stat-value">{questions.length - score}</span><span className="pv-stat-label">Wrong</span></div>
              <div className="pv-stat"><span className="pv-stat-value">{pct}%</span><span className="pv-stat-label">Score</span></div>
            </div>
            <div className="pv-results-actions">
              <Button variant="primary" onClick={() => {
                setQIndex(0); setSelected(null); setShowFeedback(false); setScore(0); setDone(false)
                setQuestions(quiz.quiz_questions.map(shuffleQuestion))
              }}>Try Again</Button>
              <Link to="/quizzes"><Button variant="secondary">Back to Quizzes</Button></Link>
            </div>
          </div>
        </div>
      </section>
    )
  }

  const q   = questions[qIndex]
  const pct = (qIndex / questions.length) * 100

  function handleSelect(i) {
    if (showFeedback) return
    setSelected(i)
    setShowFeedback(true)
    if (i === q.correct) setScore(s => s + 1)
  }

  function handleNext() {
    if (qIndex + 1 >= questions.length) { setDone(true); return }
    setQIndex(i => i + 1)
    setSelected(null)
    setShowFeedback(false)
  }

  return (
    <section className="section">
      <div className="container quiz-taker">
        <div className="quiz-taker-header">
          <Link to="/quizzes" className="pv-back"><ArrowLeft size={14} /> Quizzes</Link>
          <p className="quiz-taker-title">{quiz.title}</p>
          <div className="quiz-taker-progress">
            <div className="quiz-taker-bar"><div className="quiz-taker-bar-fill" style={{ width: `${pct}%` }} /></div>
            <span className="quiz-taker-counter">{qIndex + 1} / {questions.length}</span>
          </div>
        </div>

        <p className="quiz-question-text">{q.prompt}</p>

        <div className="pv-options-grid">
          {q.options.map((opt, i) => {
            let cls = 'pv-option'
            if (showFeedback) {
              if (i === q.correct) cls += ' pv-option--correct'
              else if (i === selected) cls += ' pv-option--wrong'
              else cls += ' pv-option--dimmed'
            }
            return (
              <button
                key={i}
                className={cls}
                style={{ backgroundColor: COLORS[i] }}
                onClick={() => handleSelect(i)}
                disabled={showFeedback}
              >
                <span className="pv-option-letter">{LETTERS[i]}</span>
                <span className="pv-option-text">{opt}</span>
              </button>
            )
          })}
        </div>

        {showFeedback && (
          <div className="pv-feedback">
            <p className={`pv-feedback-icon ${selected === q.correct ? 'pv-feedback-icon--correct' : 'pv-feedback-icon--wrong'}`}>
              {selected === q.correct
                ? <><CheckCircle size={22} /> Correct!</>
                : <><XCircle size={22} /> Incorrect</>}
            </p>
            {q.explanation && <p className="pv-explanation">{q.explanation}</p>}
            <Button variant="primary" onClick={handleNext}>
              {qIndex + 1 >= questions.length ? 'See Results' : 'Next Question'}
            </Button>
          </div>
        )}
      </div>
    </section>
  )
}
