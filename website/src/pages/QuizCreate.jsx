import { useState, useEffect } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Plus, Trash2, Copy, Check } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { createQuiz, updateQuiz, fetchQuizById } from '../lib/quizzesApi'
import Button from '../components/Button'
import './Quizzes.css'

const BLANK_Q = () => ({ prompt: '', options: ['', '', '', ''], correct: 0, explanation: '' })

export default function QuizCreate() {
  const { id }         = useParams()
  const isEdit         = Boolean(id)
  const { currentUser } = useAuth()
  const navigate       = useNavigate()

  const [title, setTitle]         = useState('')
  const [questions, setQuestions] = useState([BLANK_Q()])
  const [saving, setSaving]       = useState(false)
  const [error, setError]         = useState('')
  const [done, setDone]           = useState(null) // { code }
  const [copied, setCopied]       = useState(false)

  useEffect(() => {
    if (!currentUser) navigate('/login')
  }, [currentUser])

  useEffect(() => {
    if (!isEdit) return
    fetchQuizById(id).then(data => {
      setTitle(data.title)
      setQuestions(data.quiz_questions.length ? data.quiz_questions : [BLANK_Q()])
    }).catch(() => setError('Could not load quiz.'))
  }, [id])

  function setOption(qi, oi, value) {
    setQuestions(prev => prev.map((q, i) => i !== qi ? q : {
      ...q, options: q.options.map((o, j) => j === oi ? value : o)
    }))
  }

  function addQuestion() {
    setQuestions(prev => [...prev, BLANK_Q()])
  }

  function removeQuestion(i) {
    setQuestions(prev => prev.filter((_, j) => j !== i))
  }

  async function handleSave() {
    if (!title.trim()) { setError('Give your quiz a title.'); return }
    const valid = questions.filter(q => q.prompt.trim() && q.options.every(o => o.trim()))
    if (valid.length === 0) { setError('Add at least one complete question.'); return }
    setSaving(true); setError('')
    try {
      if (isEdit) {
        await updateQuiz(id, title.trim(), valid)
        navigate('/quizzes')
      } else {
        const quiz = await createQuiz(currentUser.id, title.trim(), valid)
        setDone({ code: quiz.code })
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  function copyCode() {
    navigator.clipboard.writeText(done.code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (done) return (
    <section className="section">
      <div className="container quiz-editor">
        <div className="quiz-success-box">
          <h2>Quiz Created! 🎉</h2>
          <p style={{ color: 'var(--muted-foreground)' }}>Share this code with anyone to take your quiz:</p>
          <div className="quiz-success-code">{done.code}</div>
          <p className="quiz-success-hint">They can enter it at <strong>incentivefinance.org/quizzes</strong></p>
          <div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap' }}>
            <Button variant="secondary" icon={copied ? Check : Copy} onClick={copyCode}>
              {copied ? 'Copied!' : 'Copy Code'}
            </Button>
            <Link to="/quizzes"><Button variant="primary">Back to Quizzes</Button></Link>
          </div>
        </div>
      </div>
    </section>
  )

  return (
    <section className="section">
      <div className="container quiz-editor">
        <div className="quiz-editor-header">
          <Link to="/quizzes" className="quiz-editor-back"><ArrowLeft size={14} /> Quizzes</Link>
        </div>
        <h1>{isEdit ? 'Edit Quiz' : 'Create a Quiz'}</h1>

        {error && <p style={{ color: 'var(--accent)', marginBottom: 16 }}>{error}</p>}

        <div className="quiz-field">
          <label>Quiz Title</label>
          <input
            type="text"
            placeholder="e.g. Budgeting Basics"
            value={title}
            onChange={e => setTitle(e.target.value)}
          />
        </div>

        <div className="quiz-questions-list">
          {questions.map((q, qi) => (
            <div key={qi} className="quiz-q-card">
              <div className="quiz-q-card-header">
                <span className="quiz-q-num">Question {qi + 1}</span>
                {questions.length > 1 && (
                  <button className="quiz-icon-btn quiz-icon-btn--danger" onClick={() => removeQuestion(qi)}>
                    <Trash2 size={14} />
                  </button>
                )}
              </div>
              <div className="quiz-field" style={{ marginBottom: 0 }}>
                <label>Question</label>
                <textarea
                  rows={2}
                  placeholder="What is compound interest?"
                  value={q.prompt}
                  onChange={e => setQuestions(prev => prev.map((x, i) => i !== qi ? x : { ...x, prompt: e.target.value }))}
                />
              </div>
              <div className="quiz-options-grid" style={{ marginTop: 14 }}>
                {q.options.map((opt, oi) => (
                  <div key={oi} className="quiz-option-row">
                    <input
                      type="radio"
                      name={`correct-${qi}`}
                      checked={q.correct === oi}
                      onChange={() => setQuestions(prev => prev.map((x, i) => i !== qi ? x : { ...x, correct: oi }))}
                      title="Mark as correct"
                    />
                    <input
                      type="text"
                      placeholder={`Option ${oi + 1}${q.correct === oi ? ' (correct)' : ''}`}
                      value={opt}
                      onChange={e => setOption(qi, oi, e.target.value)}
                    />
                  </div>
                ))}
              </div>
              <div className="quiz-field" style={{ marginTop: 14 }}>
                <label>Explanation (optional)</label>
                <input
                  type="text"
                  placeholder="Brief explanation shown after answering"
                  value={q.explanation}
                  onChange={e => setQuestions(prev => prev.map((x, i) => i !== qi ? x : { ...x, explanation: e.target.value }))}
                />
              </div>
            </div>
          ))}
        </div>

        <button className="quiz-add-q-btn" onClick={addQuestion}>
          <Plus size={18} /> Add Question
        </button>

        <div className="quiz-save-row">
          <Link to="/quizzes"><Button variant="secondary">Cancel</Button></Link>
          <Button variant="primary" onClick={handleSave} disabled={saving}>
            {saving ? 'Saving…' : isEdit ? 'Save Changes' : 'Create Quiz'}
          </Button>
        </div>
      </div>
    </section>
  )
}
