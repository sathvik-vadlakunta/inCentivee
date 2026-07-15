import { useState, useEffect, useCallback } from 'react'
import { levels } from '../data/levels'
import { useAuth } from '../context/AuthContext'
import {
  fetchQuestionsForLesson, fetchFillBlank,
  createQuestion, updateQuestion, deleteQuestion,
  upsertFillBlank, deleteFillBlank,
} from '../lib/questionsApi'
import { fetchArticles, createArticle, updateArticle, deleteArticle } from '../lib/articlesApi'
import { LogOut, ChevronDown, ChevronRight, Trash2, Plus, Save, FileText, BookOpen } from 'lucide-react'
import './Admin.css'

const BLANK_MC = { prompt: '', options: ['', '', '', ''], correct: 0, explanation: '' }
const BLANK_FB = { prompt: '', options: ['', '', '', ''], correct: 0, explanation: '' }

function QuestionCard({ q, onSave, onDelete, isFillBlank }) {
  const [draft, setDraft] = useState(q)
  const [saving, setSaving] = useState(false)
  const dirty = JSON.stringify(draft) !== JSON.stringify(q)

  useEffect(() => { setDraft(q) }, [q])

  function setOption(i, value) {
    const options = [...draft.options]
    options[i] = value
    setDraft({ ...draft, options })
  }

  async function handleSave() {
    setSaving(true)
    try {
      await onSave(draft)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="admin-qcard">
      <label className="admin-field">
        <span>{isFillBlank ? 'Prompt (use ______ where the blank goes)' : 'Prompt'}</span>
        <textarea
          value={draft.prompt}
          onChange={e => setDraft({ ...draft, prompt: e.target.value })}
          rows={2}
        />
      </label>
      <div className="admin-options">
        {draft.options.map((opt, i) => (
          <label key={i} className={`admin-option-row${draft.correct === i ? ' admin-option-row--correct' : ''}`}>
            <input
              type="radio"
              name={`correct-${draft.id ?? 'new'}`}
              checked={draft.correct === i}
              onChange={() => setDraft({ ...draft, correct: i })}
            />
            <input
              type="text"
              value={opt}
              placeholder={`Option ${i + 1}`}
              onChange={e => setOption(i, e.target.value)}
            />
          </label>
        ))}
      </div>
      <label className="admin-field">
        <span>Explanation</span>
        <textarea
          value={draft.explanation ?? ''}
          onChange={e => setDraft({ ...draft, explanation: e.target.value })}
          rows={2}
        />
      </label>
      <div className="admin-qcard-actions">
        <button className="admin-btn admin-btn--danger" onClick={() => onDelete(q)}>
          <Trash2 size={15} /> Delete
        </button>
        <button className="admin-btn admin-btn--primary" onClick={handleSave} disabled={!dirty || saving}>
          <Save size={15} /> {saving ? 'Saving…' : 'Save'}
        </button>
      </div>
    </div>
  )
}

function LessonEditor({ lessonId, unitId, title }) {
  const [questions, setQuestions] = useState(null)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    fetchQuestionsForLesson(lessonId).then(setQuestions).catch(e => setError(e.message))
  }, [lessonId])

  useEffect(() => { load() }, [load])

  async function handleSave(draft) {
    setError('')
    try {
      if (draft.id) {
        await updateQuestion(draft.id, {
          prompt: draft.prompt, options: draft.options, correct: draft.correct, explanation: draft.explanation,
        })
      } else {
        await createQuestion({
          unitId, lessonId, position: questions.length,
          prompt: draft.prompt, options: draft.options, correct: draft.correct, explanation: draft.explanation,
        })
      }
      load()
    } catch (e) {
      setError(e.message)
    }
  }

  async function handleDelete(q) {
    if (q.id && !window.confirm('Delete this question?')) return
    if (!q.id) { setQuestions(prev => prev.filter(x => x !== q)); return }
    setError('')
    try {
      await deleteQuestion(q.id)
      load()
    } catch (e) {
      setError(e.message)
    }
  }

  function addBlank() {
    setQuestions(prev => [...(prev ?? []), { ...BLANK_MC }])
  }

  if (questions === null) return <p className="admin-loading">Loading questions…</p>

  return (
    <div className="admin-lesson-editor">
      <h3>{title}</h3>
      {error && <p className="admin-error">{error}</p>}
      {questions.length === 0 && <p className="admin-empty">No questions yet.</p>}
      {questions.map((q, i) => (
        <QuestionCard key={q.id ?? `new-${i}`} q={q} onSave={handleSave} onDelete={handleDelete} />
      ))}
      <button className="admin-btn admin-btn--add" onClick={addBlank}>
        <Plus size={16} /> Add question
      </button>
    </div>
  )
}

function FillBlankEditor({ unitId, title }) {
  const [q, setQ] = useState(null)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    fetchFillBlank(unitId).then(row => setQ(row ?? { ...BLANK_FB })).catch(e => setError(e.message))
  }, [unitId])

  useEffect(() => { load() }, [load])

  async function handleSave(draft) {
    setError('')
    try {
      await upsertFillBlank(unitId, {
        prompt: draft.prompt, options: draft.options, correct: draft.correct, explanation: draft.explanation,
      })
      load()
    } catch (e) {
      setError(e.message)
    }
  }

  async function handleDelete() {
    if (!window.confirm('Delete this fill-blank question?')) return
    setError('')
    try {
      await deleteFillBlank(unitId)
      load()
    } catch (e) {
      setError(e.message)
    }
  }

  if (q === null) return <p className="admin-loading">Loading…</p>

  return (
    <div className="admin-lesson-editor">
      <h3>{title} — Fill in the blank</h3>
      {error && <p className="admin-error">{error}</p>}
      <QuestionCard q={q} onSave={handleSave} onDelete={handleDelete} isFillBlank />
    </div>
  )
}

const BLANK_ARTICLE = { title: '', author: '', body: '' }

function ArticleCard({ article, onSave, onDelete }) {
  const [draft, setDraft] = useState(article)
  const [saving, setSaving] = useState(false)
  const dirty = JSON.stringify(draft) !== JSON.stringify(article)

  useEffect(() => { setDraft(article) }, [article])

  async function handleSave() {
    setSaving(true)
    try { await onSave(draft) } finally { setSaving(false) }
  }

  return (
    <div className="admin-qcard">
      <label className="admin-field">
        <span>Title</span>
        <input type="text" value={draft.title} onChange={e => setDraft({ ...draft, title: e.target.value })} />
      </label>
      <label className="admin-field">
        <span>Author</span>
        <input type="text" value={draft.author ?? ''} placeholder="incentive team" onChange={e => setDraft({ ...draft, author: e.target.value })} />
      </label>
      <label className="admin-field">
        <span>Body</span>
        <textarea value={draft.body} onChange={e => setDraft({ ...draft, body: e.target.value })} rows={10} />
      </label>
      <div className="admin-qcard-actions">
        <button className="admin-btn admin-btn--danger" onClick={() => onDelete(article)}>
          <Trash2 size={15} /> Delete
        </button>
        <button className="admin-btn admin-btn--primary" onClick={handleSave} disabled={!dirty || saving}>
          <Save size={15} /> {saving ? 'Saving…' : 'Save'}
        </button>
      </div>
    </div>
  )
}

function ArticlesEditor() {
  const [articles, setArticles] = useState(null)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    fetchArticles().then(setArticles).catch(e => setError(e.message))
  }, [])

  useEffect(() => { load() }, [load])

  async function handleSave(draft) {
    setError('')
    try {
      if (draft.id) {
        await updateArticle(draft.id, { title: draft.title, author: draft.author, body: draft.body })
      } else {
        await createArticle({ title: draft.title, author: draft.author, body: draft.body })
      }
      load()
    } catch (e) { setError(e.message) }
  }

  async function handleDelete(article) {
    if (article.id && !window.confirm('Delete this article?')) return
    if (!article.id) { setArticles(prev => prev.filter(a => a !== article)); return }
    setError('')
    try { await deleteArticle(article.id); load() } catch (e) { setError(e.message) }
  }

  function addBlank() {
    setArticles(prev => [...(prev ?? []), { ...BLANK_ARTICLE }])
  }

  if (articles === null) return <p className="admin-loading">Loading articles…</p>

  return (
    <div className="admin-lesson-editor">
      <h3>Articles</h3>
      {error && <p className="admin-error">{error}</p>}
      {articles.length === 0 && <p className="admin-empty">No articles yet.</p>}
      {articles.map((a, i) => (
        <ArticleCard key={a.id ?? `new-${i}`} article={a} onSave={handleSave} onDelete={handleDelete} />
      ))}
      <button className="admin-btn admin-btn--add" onClick={addBlank}>
        <Plus size={16} /> New article
      </button>
    </div>
  )
}

export default function Admin() {
  const { currentUser, logOut } = useAuth()
  const [tab, setTab] = useState('questions')
  const [openUnit, setOpenUnit] = useState(null)
  const [selected, setSelected] = useState(null)

  function toggleUnit(unitId) {
    setOpenUnit(prev => prev === unitId ? null : unitId)
  }

  return (
    <main className="admin-page">
      <div className="admin-header">
        <div>
          <h1>Admin</h1>
          <p>Signed in as {currentUser?.email}</p>
        </div>
        <button className="admin-btn" onClick={logOut}><LogOut size={16} /> Log out</button>
      </div>

      <div className="admin-tabs">
        <button className={`admin-tab${tab === 'questions' ? ' admin-tab--active' : ''}`} onClick={() => setTab('questions')}>
          <BookOpen size={15} /> Questions
        </button>
        <button className={`admin-tab${tab === 'articles' ? ' admin-tab--active' : ''}`} onClick={() => setTab('articles')}>
          <FileText size={15} /> Articles
        </button>
      </div>

      {tab === 'questions' && (
        <div className="admin-layout">
          <nav className="admin-sidebar">
            {levels.map(level => (
              <div key={level.id} className="admin-level">
                <div className="admin-level-title">{level.title}</div>
                {level.units.map(unit => (
                  <div key={unit.id} className="admin-unit">
                    <button className="admin-unit-toggle" onClick={() => toggleUnit(unit.id)}>
                      {openUnit === unit.id ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                      <span>{unit.icon} {unit.title}</span>
                    </button>
                    {openUnit === unit.id && (
                      <div className="admin-lesson-list">
                        {(unit.lessons ?? []).map(lesson => (
                          <button
                            key={lesson.id}
                            className={`admin-lesson-link${selected?.lessonId === lesson.id ? ' admin-lesson-link--active' : ''}`}
                            onClick={() => setSelected({ kind: 'lesson', unitId: unit.id, lessonId: lesson.id, title: lesson.title })}
                          >
                            {lesson.title}
                          </button>
                        ))}
                        <button
                          className={`admin-lesson-link admin-lesson-link--fb${selected?.kind === 'fillBlank' && selected?.unitId === unit.id ? ' admin-lesson-link--active' : ''}`}
                          onClick={() => setSelected({ kind: 'fillBlank', unitId: unit.id, title: unit.title })}
                        >
                          Fill in the blank
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ))}
          </nav>
          <section className="admin-main">
            {!selected && <p className="admin-empty">Pick a lesson on the left to edit its questions.</p>}
            {selected?.kind === 'lesson' && (
              <LessonEditor key={selected.lessonId} lessonId={selected.lessonId} unitId={selected.unitId} title={selected.title} />
            )}
            {selected?.kind === 'fillBlank' && (
              <FillBlankEditor key={selected.unitId} unitId={selected.unitId} title={selected.title} />
            )}
          </section>
        </div>
      )}

      {tab === 'articles' && (
        <div className="admin-layout">
          <section className="admin-main admin-main--full">
            <ArticlesEditor />
          </section>
        </div>
      )}
    </main>
  )
}
