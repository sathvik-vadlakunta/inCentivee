import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { supabase } from '../lib/supabase'
import { getStoredProgress } from '../lib/guestProgress'
import { Check, LogIn, BookOpen, Star, Trophy, Lock, Download } from 'lucide-react'
import { getPurchased, getActive, getSpent, getCustomValue, setCustomValue, purchase, toggleItem } from '../lib/shop'
import './Progress.css'

const LESSON_IDS_ALL = [
  'u1-1','u1-2','u1-3','u1-4','u2-1','u2-2',
  'u2-3','u3-1','u3-2','u3-3','u4-1','u4-2',
  'u4-3','u5-1','u5-2','u6-1','u7-1','u7-2',
  'u7-3','u7-4','u7-5','u8-1','u9-1','u10-1',
  'u11-1','u12-1','u13-1','u14-1','u15-1',
  'u16-1','u17-1','u18-1','u19-1','u21-1','u22-1',
]
const CHAPTER_TEST_IDS_ALL = ['s1','s2','s3','s4','s5','s6'].map(id => `${id}-test`)

const QUESTS = [
  { id: 'q-first',   label: 'First Steps',    desc: 'Complete your first lesson', goal: 1,  getProgress: (ids)         => Math.min(LESSON_IDS_ALL.filter(id => ids.has(id)).length, 1) },
  { id: 'q-ten',     label: 'On a Roll',      desc: 'Complete 10 lessons',        goal: 10, getProgress: (ids)         => LESSON_IDS_ALL.filter(id => ids.has(id)).length },
  { id: 'q-fanatic', label: 'Finance Fanatic',desc: 'Complete 25 lessons',        goal: 25, getProgress: (ids)         => LESSON_IDS_ALL.filter(id => ids.has(id)).length },
  { id: 'q-test',    label: 'Test Taker',     desc: 'Pass a chapter test',        goal: 1,  getProgress: (ids)         => Math.min(CHAPTER_TEST_IDS_ALL.filter(id => ids.has(id)).length, 1) },
  { id: 'q-coins',   label: 'Coin Collector', desc: 'Earn 50 cents',              goal: 50, getProgress: (_ids, coins) => coins },
  { id: 'q-cap',     label: 'The Graduate',   desc: 'Complete the Capstone',      goal: 1,  getProgress: (ids)         => ids.has('capstone') ? 1 : 0 },
]

const COIN_SHAPES = [
  { id: 'circle',  label: 'Circle',  d: null },
  { id: 'star',    label: 'Star',    d: 'M44.2,11.5 Q50,3 55.8,11.5 L66.5,27.4 L84.8,32.7 Q94.7,35.5 88.4,43.6 L76.6,58.7 L77.2,77.8 Q77.6,88 67.9,84.5 L50,78 L32.1,84.5 Q22.4,88 22.8,77.8 L23.4,58.7 L11.6,43.6 Q5.3,35.5 15.2,32.7 L33.5,27.4 Z' },
  { id: 'hexagon', label: 'Hexagon', d: 'M43.9,6.5 Q50,3 56.1,6.5 L84.6,23 Q90.7,26.5 90.7,33.5 L90.7,66.5 Q90.7,73.5 84.6,77 L56.1,93.5 Q50,97 43.9,93.5 L15.4,77 Q9.3,73.5 9.3,66.5 L9.3,33.5 Q9.3,26.5 15.4,23 Z' },
  { id: 'diamond', label: 'Diamond', d: 'M41.5,11.5 Q50,3 58.5,11.5 L88.5,41.5 Q97,50 88.5,58.5 L58.5,88.5 Q50,97 41.5,88.5 L11.5,58.5 Q3,50 11.5,41.5 Z' },
  { id: 'shield',  label: 'Shield',  d: 'M12,10 Q50,5 88,10 C96,15 97,40 90,65 C82,82 65,93 50,97 C35,93 18,82 10,65 C3,40 4,15 12,10 Z' },
]

function CoinSVG({ shape, size = 28, stroke = 'var(--foreground)', strokeWidth, drop, style }) {
  const sw = strokeWidth ?? Math.round(200 / size)
  const filter = drop ? `drop-shadow(${drop} var(--foreground))` : undefined
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" aria-hidden="true"
         style={{ display: 'block', flexShrink: 0, filter, ...style }}>
      {shape.id === 'circle'
        ? <circle cx="50" cy="50" r="44" fill="url(#coin-grad)" stroke={stroke} strokeWidth={sw}/>
        : <path d={shape.d} fill="url(#coin-grad)" stroke={stroke} strokeWidth={sw}/>}
    </svg>
  )
}

const SHOP_ITEMS = [
  { id: 'custom-accent',   type: 'color', storageKey: 'accent',     label: 'Accent Color',      desc: 'Choose the color of buttons, highlights, and branded elements', price: 30, defaultColor: '#FF6F61' },
  { id: 'custom-nav',      type: 'color', storageKey: 'nav',        label: 'Navbar Color',       desc: 'Pick any color for your navbar background',                     price: 20, defaultColor: '#1E293B' },
  { id: 'custom-coin',     type: 'shape', storageKey: 'coin_shape', label: 'Coin Shape',         desc: 'Choose the shape of every coin badge throughout the site',      price: 25 },
  { id: 'custom-progress', type: 'color', storageKey: 'progress',   label: 'Progress Bar Color', desc: 'Personalize the color of all progress and XP bars',            price: 20, defaultColor: '#F59E0B' },
]

function buildCertHtml({ name, lessonsCount, testsCount, coins, date }) {
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>InCentive Certificate of Completion</title>
<link href="https://fonts.googleapis.com/css2?family=Nunito:wght@400;700;800;900&display=swap" rel="stylesheet">
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  body{font-family:'Nunito',Georgia,serif;background:#FFFDF5;display:flex;align-items:center;justify-content:center;min-height:100vh;padding:40px}
  .cert{width:800px;padding:64px 72px;border:5px solid #1a1a1a;box-shadow:10px 10px 0 #1a1a1a;background:#fff;text-align:center}
  .brand{font-size:13px;text-transform:uppercase;letter-spacing:.18em;font-weight:800;color:#888;margin-bottom:28px}
  .divider{width:72px;height:5px;background:#FF6F61;margin:20px auto;border-radius:3px}
  .cert-title{font-size:40px;font-weight:900;color:#1a1a1a;margin-bottom:8px}
  .cert-subtitle{font-size:16px;color:#888;margin-bottom:28px}
  .cert-name{font-size:52px;font-weight:900;color:#FF6F61;border-bottom:4px solid #1a1a1a;padding-bottom:10px;margin-bottom:28px;display:inline-block;min-width:400px}
  .cert-body{font-size:17px;color:#444;line-height:1.7;margin-bottom:36px}
  .stats{display:flex;gap:24px;justify-content:center;margin-bottom:40px}
  .stat{background:#FFFDF5;border:3px solid #1a1a1a;border-radius:12px;padding:16px 28px;box-shadow:4px 4px 0 #1a1a1a}
  .stat-n{font-size:34px;font-weight:900;color:#1a1a1a}
  .stat-l{font-size:11px;color:#888;font-weight:800;text-transform:uppercase;letter-spacing:.07em;margin-top:2px}
  .cert-date{font-size:13px;color:#aaa;margin-top:8px}
  @media print{body{padding:0}@page{margin:0}.cert{box-shadow:none;border-width:4px}}
</style>
</head>
<body>
<div class="cert">
  <div class="brand">incentive &middot; financial literacy</div>
  <div class="divider"></div>
  <h1 class="cert-title">Certificate of Completion</h1>
  <p class="cert-subtitle">This certifies that</p>
  <div class="cert-name">${name}</div>
  <p class="cert-body">
    has successfully completed the <strong>InCentive Financial Literacy</strong> program,<br>
    demonstrating knowledge of personal finance, investing, budgeting, and more.
  </p>
  <div class="stats">
    <div class="stat"><div class="stat-n">${lessonsCount}</div><div class="stat-l">Lessons</div></div>
    <div class="stat"><div class="stat-n">${testsCount}</div><div class="stat-l">Tests Passed</div></div>
    <div class="stat"><div class="stat-n">${coins}&cent;</div><div class="stat-l">Cents Earned</div></div>
  </div>
  <div class="divider"></div>
  <p class="cert-date">Issued ${date} &middot; incentivefinance.org</p>
</div>
</body>
</html>`
}

export default function Progress() {
  const { currentUser, profile } = useAuth()
  const [completedIds, setCompletedIds] = useState(() =>
    currentUser ? new Set() : getStoredProgress()
  )
  const [purchased,     setPurchased]     = useState(getPurchased)
  const [active,        setActiveSet]     = useState(getActive)
  const [spent,         setSpent]         = useState(getSpent)
  const [customValues,  setCustomValues]  = useState(() => ({
    accent:     getCustomValue('accent',     '#FF6F61'),
    nav:        getCustomValue('nav',        '#1E293B'),
    coin_shape: getCustomValue('coin_shape', 'circle'),
    progress:   getCustomValue('progress',   '#F59E0B'),
  }))

  function refreshShop() {
    setPurchased(getPurchased())
    setActiveSet(getActive())
    setSpent(getSpent())
  }

  function handleCustom(key, value) {
    setCustomValue(key, value)
    setCustomValues(prev => ({ ...prev, [key]: value }))
  }

  useEffect(() => {
    if (!currentUser) return
    supabase
      .from('lesson_progress')
      .select('lesson_id')
      .eq('user_id', currentUser.id)
      .eq('completed', true)
      .then(({ data }) => {
        if (data) setCompletedIds(new Set(data.map(r => r.lesson_id)))
      })
  }, [currentUser?.id])

  const activeShape  = COIN_SHAPES.find(s => s.id === (customValues.coin_shape || 'circle')) ?? COIN_SHAPES[0]
  const earned       = profile?.xp ?? 0
  const coins        = Math.max(0, earned - spent)
  const xp           = earned * 2
  const lessonsCount = LESSON_IDS_ALL.filter(id => completedIds.has(id)).length
  const testsCount   = CHAPTER_TEST_IDS_ALL.filter(id => completedIds.has(id)).length

  function openCertificate() {
    const name = profile?.name ?? currentUser?.email?.split('@')[0] ?? 'Student'
    const date = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
    const html = buildCertHtml({ name, lessonsCount, testsCount, coins, date })
    const win  = window.open('', '_blank', 'width=960,height=760')
    if (win) {
      win.document.write(html)
      win.document.close()
      setTimeout(() => win.print(), 800)
    }
  }

  function handleBuy(item) {
    purchase(item.id, item.price)
    refreshShop()
  }

  function handleToggle(item) {
    toggleItem(item.id, !active.has(item.id))
    refreshShop()
  }

  return (
    <main className="progress-page">
      <div className="container">

        <div className="progress-header">
          <h1 className="progress-title">Progress</h1>
          {!currentUser && (
            <Link to="/login" className="btn btn-primary">
              <span className="btn-label">Log in to track</span>
              <span className="btn-icon-badge"><LogIn size={16} strokeWidth={2.5} /></span>
            </Link>
          )}
        </div>

        {/* Stats */}
        <div className="progress-stats">
          <div className="stat-card">
            <CoinSVG shape={activeShape} size={42} drop="2px 2px 0" />
            <div className="stat-body">
              <span className="stat-value">{coins}</span>
              <span className="stat-label">Cents earned</span>
            </div>
          </div>
          <div className="stat-card">
            <span className="stat-icon stat-icon--xp"></span>
            <div className="stat-body">
              <span className="stat-value">{xp}</span>
              <span className="stat-label">XP</span>
            </div>
          </div>
          <div className="stat-card">
            <span className="stat-icon stat-icon--lessons"><BookOpen size={18} strokeWidth={2.5} /></span>
            <div className="stat-body">
              <span className="stat-value">{lessonsCount}</span>
              <span className="stat-label">Lessons done</span>
            </div>
          </div>
          <div className="stat-card">
            <span className="stat-icon stat-icon--tests"><Star size={18} strokeWidth={2.5} /></span>
            <div className="stat-body">
              <span className="stat-value">{testsCount}</span>
              <span className="stat-label">Tests passed</span>
            </div>
          </div>
        </div>

        {/* Certificate achievement */}
        {(() => {
          const earned = completedIds.has('capstone')
          return (
            <div className={`cert-achievement${earned ? ' cert-achievement--earned' : ''}`}>
              <div className={`cert-achievement-icon${earned ? ' cert-achievement-icon--earned' : ''}`}>
                {earned ? <Trophy size={28} strokeWidth={2.5} /> : <Lock size={24} strokeWidth={2.5} />}
              </div>
              <div className="cert-achievement-text">
                <span className="cert-achievement-label">Finance Certificate</span>
                <span className="cert-achievement-desc">
                  {earned
                    ? 'You completed the Capstone Challenge — your certificate is ready.'
                    : 'Complete the Capstone Challenge to earn your certificate of financial literacy.'}
                </span>
              </div>
              <button
                className={`btn ${earned ? 'btn-primary' : 'btn-secondary'} cert-achievement-btn`}
                disabled={!earned}
                onClick={earned ? openCertificate : undefined}
              >
                <span className="btn-label">{earned ? 'Download' : 'Locked'}</span>
                <span className="btn-icon-badge">
                  {earned ? <Download size={15} strokeWidth={2.5} /> : <Lock size={15} strokeWidth={2.5} />}
                </span>
              </button>
            </div>
          )
        })()}

        <div className="progress-columns">

          {/* QUESTS */}
          <section className="progress-section">
            <h2 className="progress-section-title">Quests</h2>
            <div className="quests-grid">
              {QUESTS.map(q => {
                const progress = q.getProgress(completedIds, coins)
                const pct  = Math.min(Math.round((progress / q.goal) * 100), 100)
                const done = progress >= q.goal
                return (
                  <div key={q.id} className={`quest-card${done ? ' quest-card--done' : ''}`}>
                    <div className="quest-card-top">
                      <div className={`quest-check${done ? ' quest-check--done' : ''}`}>
                        {done && <Check size={13} strokeWidth={3} />}
                      </div>
                      <div className="quest-card-text">
                        <span className="quest-card-label">{q.label}</span>
                        <span className="quest-card-desc">{q.desc}</span>
                      </div>
                      <span className="quest-card-count">{Math.min(progress, q.goal)}/{q.goal}</span>
                    </div>
                    <div className="quest-bar-track">
                      <div className="quest-bar-fill" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                )
              })}
            </div>
          </section>

          {/* SHOP */}
          <section className="progress-section">
            <h2 className="progress-section-title">
              Shop
              <span className="shop-balance">
                <CoinSVG shape={activeShape} size={20} drop="1px 1px 0" />
                {coins} available
              </span>
            </h2>
            <div className="shop-grid">
              {SHOP_ITEMS.map(item => {
                const owned    = purchased.has(item.id)
                const isActive = active.has(item.id)
                const canBuy   = !owned && coins >= item.price
                const curColor = item.type === 'color' ? (customValues[item.storageKey] || item.defaultColor) : null
                const curShape = item.type === 'shape' ? (customValues.coin_shape || 'circle') : null

                return (
                  <div key={item.id} className={`shop-card${isActive ? ' shop-card--active' : ''}`}>

                    {/* preview strip */}
                    {item.type === 'color' && (
                      <div className="shop-swatch" style={{ background: owned && isActive ? curColor : item.defaultColor }}>
                        {isActive && <span className="shop-active-tag"><Check size={10} strokeWidth={3} /> Active</span>}
                      </div>
                    )}
                    {item.type === 'shape' && (
                      <div className="shop-swatch shop-swatch--shapes">
                        {COIN_SHAPES.map(s => (
                          <CoinSVG key={s.id} shape={s} size={32}
                            style={{ opacity: (owned && isActive && curShape === s.id) ? 1 : 0.55 }}
                          />
                        ))}
                        {isActive && <span className="shop-active-tag"><Check size={10} strokeWidth={3} /> Active</span>}
                      </div>
                    )}

                    <div className="shop-card-body">
                      <span className="shop-card-label">{item.label}</span>
                      <p className="shop-card-desc">{item.desc}</p>
                    </div>

                    {/* controls when active */}
                    {owned && isActive && item.type === 'color' && (
                      <div className="shop-controls">
                        <input
                          type="color"
                          className="shop-color-picker"
                          value={curColor}
                          onChange={e => handleCustom(item.storageKey, e.target.value)}
                        />
                        <span className="shop-controls-hint">Pick a color</span>
                      </div>
                    )}
                    {owned && isActive && item.type === 'shape' && (
                      <div className="shop-controls">
                        <div className="shop-shape-grid">
                          {COIN_SHAPES.map(s => (
                            <button
                              key={s.id}
                              className={`shop-shape-btn${curShape === s.id ? ' shop-shape-btn--selected' : ''}`}
                              title={s.label}
                              onClick={() => handleCustom('coin_shape', s.id)}
                            >
                              <CoinSVG shape={s} size={30}/>
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    <div className="shop-card-footer">
                      {owned ? (
                        <button
                          className={`btn ${isActive ? 'btn-secondary' : 'btn-primary'} shop-btn`}
                          onClick={() => handleToggle(item)}
                        >
                          <span className="btn-label">{isActive ? 'Deactivate' : 'Apply'}</span>
                        </button>
                      ) : (
                        <>
                          <span className="shop-price">
                            <CoinSVG shape={activeShape} size={28} drop="2px 2px 0" />
                            {item.price}
                          </span>
                          <button
                            className={`btn ${canBuy ? 'btn-primary' : 'btn-secondary'} shop-btn`}
                            disabled={!canBuy}
                            onClick={() => canBuy && handleBuy(item)}
                          >
                            <span className="btn-label">{canBuy ? 'Buy' : 'Need more ¢'}</span>
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </section>

        </div>
      </div>

    </main>
  )
}
