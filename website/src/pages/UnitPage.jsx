import React, { useState, useEffect, useMemo } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, Check, Lock, LogIn, Star } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { supabase } from '../lib/supabase'
import { getStoredProgress, storeProgress } from '../lib/guestProgress'
import { allUnits } from '../data/levels'
import './Learn.css'
import './UnitPage.css'

// Section metadata needed to show "Unit X of N" and colors
const SECTIONS = [
  { id: 's1', label: 'The Basics', color: '#FF6F61',
    unitIds: ['u1-1','u1-2','u1-3','u1-4','u2-1','u2-2'] },
  { id: 's2', label: 'Banking & Budgeting', color: '#0D9488',
    unitIds: ['u2-3','u3-1','u3-2','u3-3','u4-1','u4-2'] },
  { id: 's3', label: 'Taxes & Investing', color: '#F59E0B',
    unitIds: ['u4-3','u5-1','u5-2','u6-1','u7-1','u7-2'] },
  { id: 's4', label: 'Markets & Business', color: '#3B82F6',
    unitIds: ['u7-3','u7-4','u7-5','u8-1','u9-1','u10-1'] },
  { id: 's5', label: 'Advanced Topics', color: '#8B5CF6',
    unitIds: ['u11-1','u12-1','u13-1','u14-1','u15-1'] },
  { id: 's6', label: 'Finance & Psychology', color: '#6366F1',
    unitIds: ['u16-1','u17-1','u18-1','u19-1','u21-1','u22-1'] },
]

const NODE_R       = 30
const TRAIL_CENTER = 150
const TRAIL_TOP    = 48
const LESSON_ZIGZAG = [0, -52, 52, -52, 0, 52, -52, 52]
const LESSON_INTERVAL = 160

function calcPositions(count, zigzag = LESSON_ZIGZAG) {
  return Array.from({ length: count }, (_, i) => ({
    x: TRAIL_CENTER + zigzag[i % zigzag.length],
    y: TRAIL_TOP + i * LESSON_INTERVAL,
  }))
}

function NodeConnector({ p1, p2, done, color }) {
  const y1 = p1.y + NODE_R
  const y2 = p2.y - NODE_R
  const h  = y2 - y1
  if (h <= 0) return null
  const minX = Math.min(p1.x, p2.x) - 8
  const maxX = Math.max(p1.x, p2.x) + 8
  const w  = Math.max(maxX - minX, 16)
  return (
    <svg style={{ position:'absolute', left:minX, top:y1, pointerEvents:'none', overflow:'visible' }} width={w} height={h}>
      <path
        d={`M ${p1.x - minX} 0 C ${p1.x - minX} ${h*0.45} ${p2.x - minX} ${h*0.55} ${p2.x - minX} ${h}`}
        fill="none" stroke={done ? color : 'rgba(0,0,0,0.11)'}
        strokeWidth="3.5" strokeDasharray={done ? 'none' : '8 6'} strokeLinecap="round"
      />
    </svg>
  )
}

function fisherYates(arr) {
  const a = [...arr]
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[a[i], a[j]] = [a[j], a[i]]
  }
  return a
}

function shuffleOptions(questions) {
  return questions.map(q => {
    const correct = q.options[q.correct]
    const opts    = fisherYates(q.options)
    return { ...q, options: opts, correct: opts.indexOf(correct) }
  })
}

function SparkleEffect({ color }) {
  return (
    <div className="sparkle-effect" aria-hidden>
      {[0,45,90,135,180,225,270,315].map((deg, i) => {
        const rad = deg * Math.PI / 180
        return (
          <div key={i} className="sparkle-particle" style={{
            '--tx': `${Math.cos(rad)*34}px`, '--ty': `${Math.sin(rad)*34}px`,
            '--spark-color': color, animationDelay: `${i*0.025}s`,
          }} />
        )
      })}
    </div>
  )
}

export default function UnitPage() {
  const { unitId } = useParams()
  const navigate   = useNavigate()
  const { currentUser, bumpXP } = useAuth()

  const unit = useMemo(() => allUnits.find(u => u.id === unitId), [unitId])

  const sectionMeta = useMemo(() => {
    for (let i = 0; i < SECTIONS.length; i++) {
      const pos = SECTIONS[i].unitIds.indexOf(unitId)
      if (pos >= 0) return { section: SECTIONS[i], unitIndex: pos + 1, unitTotal: SECTIONS[i].unitIds.length }
    }
    return null
  }, [unitId])

  const color = sectionMeta?.section.color ?? '#FF6F61'

  const [completedIds,  setCompletedIds]  = useState(() => currentUser ? getStoredProgress() : new Set())
  const [activeLesson,  setActiveLesson]  = useState(null)
  const [shuffledQs,    setShuffledQs]    = useState([])
  const [qIndex,        setQIndex]        = useState(0)
  const [selected,      setSelected]      = useState(null)
  const [showFeedback,  setShowFeedback]  = useState(false)
  const [sessionOK,     setSessionOK]     = useState(0)
  const [lessonDone,    setLessonDone]    = useState(false)
  const [centsEarned,   setCentsEarned]   = useState(0)
  const [finalScore,    setFinalScore]    = useState({ correct: 0, total: 0 })
  const [sparklingId,   setSparklingId]   = useState(null)

  useEffect(() => {
    if (!currentUser || !unit?.lessons) return
    const lessonIds = unit.lessons.map(l => l.id)
    supabase.from('lesson_progress').select('lesson_id')
      .eq('user_id', currentUser.id).eq('completed', true)
      .in('lesson_id', lessonIds)
      .then(({ data }) => {
        if (!data) return
        const supabaseIds = new Set(data.map(r => r.lesson_id))
        setCompletedIds(supabaseIds)
        storeProgress(supabaseIds)
      })
  }, [currentUser?.id, unitId])

  useEffect(() => {
    if (!activeLesson || lessonDone || showFeedback) return
    function onKey(e) {
      const n = parseInt(e.key)
      const q = shuffledQs[qIndex]
      if (n >= 1 && n <= 4 && q?.options[n-1] !== undefined) { setSelected(n-1); setShowFeedback(true) }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [activeLesson, lessonDone, showFeedback, qIndex, shuffledQs])

  if (!unit?.lessons) {
    return (
      <main className="learn-page">
        <div className="unit-not-found">
          <p>Unit not found or has no lessons yet.</p>
          <Link to="/learn" state={{ sectionIndex: Math.max(0, SECTIONS.findIndex(s => s.unitIds.includes(unitId))) }}>Back to path</Link>
        </div>
      </main>
    )
  }

  const lessons  = unit.lessons
  const positions = calcPositions(lessons.length, unit.zigzag)
  const trailH   = positions[positions.length - 1].y + NODE_R + 80

  function isUnlocked(lessonId) {
    if (!currentUser) return true
    const idx = lessons.findIndex(l => l.id === lessonId)
    if (idx <= 0) return true
    return lessons.slice(0, idx).every(l => completedIds.has(l.id))
  }

  function startLesson(lesson) {
    const qs = shuffleOptions([...lesson.questions])
    setActiveLesson(lesson)
    setShuffledQs(qs)
    setQIndex(0); setSelected(null); setShowFeedback(false)
    setSessionOK(0); setLessonDone(false); setCentsEarned(0)
    setFinalScore({ correct: 0, total: 0 })
  }

  function handleNodeClick(lesson) {
    if (!isUnlocked(lesson.id) || sparklingId) return
    setSparklingId(lesson.id)
    setTimeout(() => { setSparklingId(null); startLesson(lesson) }, 500)
  }

  function handleAnswer(i) {
    if (showFeedback) return
    setSelected(i); setShowFeedback(true)
  }

  async function handleNext() {
    const q  = shuffledQs[qIndex]
    const ok = sessionOK + (selected === q.correct ? 1 : 0)
    if (qIndex + 1 < shuffledQs.length) {
      setSessionOK(ok); setQIndex(i => i + 1); setSelected(null); setShowFeedback(false)
    } else {
      await finishLesson(ok, shuffledQs.length)
    }
  }

  async function finishLesson(correct, total) {
    const lesson      = activeLesson
    const score       = Math.round((correct / total) * 100)
    const earned      = Math.round((lesson.centsReward ?? 0) * (correct / total))
    const newCompleted = new Set([...completedIds, lesson.id])

    const allDone = lessons.every(l => newCompleted.has(l.id))
    if (allDone) newCompleted.add(unit.id)

    if (currentUser) {
      storeProgress(newCompleted)
      await supabase.from('lesson_progress').upsert({
        user_id: currentUser.id, lesson_id: lesson.id,
        completed: true, score, completed_at: new Date().toISOString(),
      })
      if (allDone) {
        await supabase.from('lesson_progress').upsert({
          user_id: currentUser.id, lesson_id: unit.id,
          completed: true, score: 100, completed_at: new Date().toISOString(),
        })
      }
      bumpXP(earned)
    }

    setCompletedIds(newCompleted)
    setCentsEarned(earned)
    setFinalScore({ correct, total })
    setLessonDone(true)
  }

  function exitLesson() { setActiveLesson(null); setLessonDone(false) }

  const completedCount = lessons.filter(l => completedIds.has(l.id)).length
  const nextUpIndex    = lessons.findIndex(l => !completedIds.has(l.id) && isUnlocked(l.id))

  /* ── DONE SCREEN ── */
  if (activeLesson && lessonDone) {
    return (
      <main className="learn-page">
        <section className="section"><div className="container">
          <div className="lesson-done">
            <div className="done-icon">
              <Check size={36} strokeWidth={3} />
            </div>
            <h2>Nice work.</h2>
            <p className="done-subtitle">{activeLesson.title}</p>
            <div className="done-cents">
              <span className="cents-coin">¢</span>
              <span>+{centsEarned} cents earned</span>
            </div>
            {!currentUser && (
              <div className="done-guest-cta">
                <p>Log in to save your progress and keep those cents.</p>
                <Link to="/login" className="btn btn-primary">
                  <span className="btn-label">Log in to save</span>
                  <span className="btn-icon-badge"><LogIn size={16} strokeWidth={2.5}/></span>
                </Link>
              </div>
            )}
            <button className="btn btn-secondary" onClick={exitLesson}>
              <span className="btn-label">Back to lessons</span>
              <span className="btn-icon-badge"><ArrowLeft size={16} strokeWidth={2.5}/></span>
            </button>
          </div>
        </div></section>
      </main>
    )
  }

  /* ── ACTIVE QUIZ ── */
  if (activeLesson) {
    const q         = shuffledQs[qIndex]
    const isCorrect = selected === q?.correct
    const pct       = (qIndex / shuffledQs.length) * 100
    const lessonNum = lessons.findIndex(l => l.id === activeLesson.id) + 1
    return (
      <main className="learn-page">
        <section className="section"><div className="container">
          <div className="lesson-shell">
            <div className="lesson-top">
              <button className="lesson-exit" onClick={exitLesson}>
                <ArrowLeft size={20} strokeWidth={2.5}/><span>Exit</span>
              </button>
              <div className="lesson-progress-track">
                <div className="lesson-progress-fill" style={{ width:`${pct}%` }}/>
              </div>
              <span className="lesson-counter">{qIndex+1} / {shuffledQs.length}</span>
            </div>
            <div className="lesson-meta">
              <span className="lesson-title-inline">{activeLesson.title}</span>
              <span className="unit-lesson-badge" style={{ '--badge-color': color }}>
                Lesson {lessonNum} of {lessons.length}
              </span>
            </div>
            <p className="lesson-prompt">{q?.prompt}</p>
            <ul className="lesson-options">
              {q?.options.map((opt, i) => {
                let cls = 'lesson-option'
                if (showFeedback) { if (i===q.correct) cls+=' correct'; else if (i===selected) cls+=' wrong' }
                else if (i===selected) cls+=' selected'
                return (
                  <li key={i}>
                    <button className={cls} onClick={() => handleAnswer(i)} disabled={showFeedback}>
                      <span className="option-letter">{i+1}</span>{opt}
                    </button>
                  </li>
                )
              })}
            </ul>
            {showFeedback && (
              <div className={`lesson-feedback ${isCorrect ? 'feedback-correct' : 'feedback-wrong'}`}>
                <p className="feedback-label">{isCorrect ? 'Correct' : 'Not quite'}</p>
                <p className="feedback-explain">{q?.explanation}</p>
                <button className="btn btn-primary" onClick={handleNext}>
                  <span className="btn-label">{qIndex+1 < shuffledQs.length ? 'Next' : 'Finish'}</span>
                  <span className="btn-icon-badge">
                    <ArrowLeft size={18} strokeWidth={2.5} style={{ transform:'rotate(180deg)' }}/>
                  </span>
                </button>
              </div>
            )}
          </div>
        </div></section>
      </main>
    )
  }

  /* ── LESSON PATH ── */
  return (
    <main className="learn-page">
      <div className="path-page">

        <div className="path-side path-side--left" aria-hidden="true">
          <div className="side-shape side-shape--pill"   style={{ top:'12%',  left:'25%' }}/>
          <div className="side-shape side-shape--tri"    style={{ top:'38%', left:'40%' }}/>
          <div className="side-shape side-shape--square" style={{ top:'65%', left:'15%' }}/>
        </div>

        <div className="path-center">
          {/* Unit banner */}
          <div className="section-banner" style={{ background: color }}>
            <div className="banner-nav">
              <button className="banner-arrow" onClick={() => navigate('/learn', { state: { sectionIndex: SECTIONS.findIndex(s => s.unitIds.includes(unitId)) } })} aria-label="Back to path">
                <ArrowLeft size={18} strokeWidth={2.5}/>
              </button>
              <span className="banner-eyebrow">
                {sectionMeta
                  ? `Unit ${sectionMeta.unitIndex} of ${sectionMeta.unitTotal} · ${sectionMeta.section.label}`
                  : 'Unit'}
              </span>
              <div style={{ width: 30 }} />
            </div>
            <h2 className="banner-title">{unit.title}</h2>
            <p className="banner-desc">{completedCount} of {lessons.length} lessons completed</p>
            {currentUser && (
              <div className="banner-progress">
                <div className="banner-progress-track">
                  <div className="banner-progress-fill"
                    style={{ width: `${lessons.length > 0 ? (completedCount / lessons.length) * 100 : 0}%` }}/>
                </div>
                <span className="banner-progress-label">{completedCount} / {lessons.length}</span>
              </div>
            )}
          </div>

          {/* Lesson trail */}
          <div className="trail-wrap">
            <div className="path-trail" style={{ height: trailH }}>
              {positions.slice(0, -1).map((p1, i) => (
                <NodeConnector key={i} p1={p1} p2={positions[i+1]}
                  done={completedIds.has(lessons[i].id) && completedIds.has(lessons[i+1].id)}
                  color={color}
                />
              ))}
              {lessons.map((lesson, i) => {
                const pos       = positions[i]
                const done      = completedIds.has(lesson.id)
                const unlocked  = isUnlocked(lesson.id)
                const sparkling = sparklingId === lesson.id
                const isNextUp  = i === nextUpIndex
                return (
                  <div key={lesson.id} className="trail-stop unit-trail-stop"
                    style={{ left: pos.x, top: pos.y - NODE_R }}>
                    {isNextUp && (
                      <div className="trail-tip" style={{ '--tip-color': color }}>
                        {completedCount === 0 ? 'START' : 'CONTINUE'}
                      </div>
                    )}
                    <button
                      className={`path-node path-node--sm ${sparkling ? 'node-sparkling' : done ? 'node-done' : unlocked ? 'node-available' : 'node-locked'}`}
                      style={{ '--node-color': color }}
                      onClick={() => handleNodeClick(lesson)}
                      disabled={!unlocked || !!sparklingId}
                      aria-label={lesson.title}
                    >
                      {sparkling && <SparkleEffect color={color}/>}
                      {done
                        ? <Check size={22} strokeWidth={3}/>
                        : !unlocked ? <Lock size={18}/>
                        : <span className="node-num">{i+1}</span>}
                    </button>
                    <div className="node-chip node-chip--sm" style={{'--chip-color': color}}>
                      <span className="node-chip-name">{lesson.title}</span>
                      <span className="node-coin-badge">¢</span>
                      <span className="node-chip-cents">{lesson.centsReward}</span>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>

        <div className="path-side path-side--right" aria-hidden="true">
          <div className="side-shape side-shape--tri"    style={{ top:'10%', left:'32%' }}/>
          <div className="side-shape side-shape--square" style={{ top:'42%', left:'50%' }}/>
          <div className="side-shape side-shape--pill"   style={{ top:'70%', left:'20%' }}/>
        </div>

      </div>
    </main>
  )
}
