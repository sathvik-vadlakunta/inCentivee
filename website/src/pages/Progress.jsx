import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { supabase } from '../lib/supabase'
import { getStoredProgress } from '../lib/guestProgress'
import { Check, LogIn, BookOpen, Star, Trophy, Lock, Download } from 'lucide-react'
import {
  getPurchased, getActive, getSpent, getPeakCoins, updatePeakCoins,
  purchase, activateItem, deactivateColor, deactivateShape,
  applyCosmetics, THEME_COLORS, COIN_SHAPES,
} from '../lib/shop'
import { saveShopToCloud } from '../lib/shopSync'
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

const S1 = ['u1-1','u1-2','u1-3','u1-4','u2-1','u2-2']
const S2 = ['u2-3','u3-1','u3-2','u3-3','u4-1','u4-2']
const S3 = ['u4-3','u5-1','u5-2','u6-1','u7-1','u7-2']
const S4 = ['u7-3','u7-4','u7-5','u8-1','u9-1','u10-1']

const lessonCount = ids => LESSON_IDS_ALL.filter(id => ids.has(id)).length
const testCount   = ids => CHAPTER_TEST_IDS_ALL.filter(id => ids.has(id)).length

const QUESTS = [
  // Lesson milestones
  { id: 'q-first',     label: 'First Steps',      desc: 'Complete your first lesson',   goal: 1,   getProgress: ids         => Math.min(lessonCount(ids), 1) },
  { id: 'q-five',      label: 'Getting Started',  desc: 'Complete 5 lessons',           goal: 5,   getProgress: ids         => lessonCount(ids) },
  { id: 'q-ten',       label: 'On a Roll',        desc: 'Complete 10 lessons',          goal: 10,  getProgress: ids         => lessonCount(ids) },
  { id: 'q-twenty',    label: 'Halfway There',    desc: 'Complete 20 lessons',          goal: 20,  getProgress: ids         => lessonCount(ids) },
  { id: 'q-fanatic',   label: 'Finance Fanatic',  desc: 'Complete 25 lessons',          goal: 25,  getProgress: ids         => lessonCount(ids) },
  { id: 'q-all',       label: 'The Full Course',  desc: 'Complete all 35 lessons',      goal: 35,  getProgress: ids         => lessonCount(ids) },
  // Section completion
  { id: 'q-basics',    label: 'Back to Basics',   desc: 'Finish The Basics section',    goal: S1.length, getProgress: ids  => S1.filter(id => ids.has(id)).length },
  { id: 'q-banking',   label: 'Money Manager',    desc: 'Finish Banking & Budgeting',   goal: S2.length, getProgress: ids  => S2.filter(id => ids.has(id)).length },
  { id: 'q-taxes',     label: 'Tax Season',       desc: 'Finish Taxes & Investing',     goal: S3.length, getProgress: ids  => S3.filter(id => ids.has(id)).length },
  { id: 'q-markets',   label: 'Market Watcher',   desc: 'Finish Markets & Business',    goal: S4.length, getProgress: ids  => S4.filter(id => ids.has(id)).length },
  // Tests
  { id: 'q-test',      label: 'Test Taker',       desc: 'Pass a chapter test',          goal: 1,  getProgress: ids          => Math.min(testCount(ids), 1) },
  { id: 'q-tests-3',   label: 'Quiz Whiz',        desc: 'Pass 3 chapter tests',         goal: 3,  getProgress: ids          => testCount(ids) },
  { id: 'q-tests-all', label: 'Chapter Champion', desc: 'Pass all 6 chapter tests',     goal: 6,  getProgress: ids          => testCount(ids) },
  // XP milestones (never decreases)
  { id: 'q-xp-100',    label: 'XP Grinder',       desc: 'Earn 100 XP',                  goal: 100,  getProgress: (_i, _c, _p, xp) => xp },
  { id: 'q-xp-200',    label: 'XP Hunter',        desc: 'Earn 200 XP',                  goal: 200,  getProgress: (_i, _c, _p, xp) => xp },
  { id: 'q-xp-1000',   label: 'XP Legend',        desc: 'Earn 1,000 XP',                goal: 1000, getProgress: (_i, _c, _p, xp) => xp },
  // Coin inventory (peak balance ever held — never decreases)
  { id: 'q-hold-100',  label: 'Saving Up',        desc: 'Hold 100 cents at once',       goal: 100,  getProgress: (_i, _c, _p, _x, peak) => peak },
  { id: 'q-hold-500',  label: 'Piggy Bank',       desc: 'Hold 500 cents at once',       goal: 500,  getProgress: (_i, _c, _p, _x, peak) => peak },
  { id: 'q-hold-1000', label: 'Vault',            desc: 'Hold 1,000 cents at once',     goal: 1000, getProgress: (_i, _c, _p, _x, peak) => peak },
  { id: 'q-hold-2000', label: 'Fort Knox',        desc: 'Hold 2,000 cents at once',     goal: 2000, getProgress: (_i, _c, _p, _x, peak) => peak },
  // Shop
  { id: 'q-shop',      label: 'Window Shopper',   desc: 'Buy something from the shop',  goal: 1,  getProgress: (_i, _c, pur) => pur.size > 0 ? 1 : 0 },
  // Capstone
  { id: 'q-cap',       label: 'The Graduate',     desc: 'Complete the Capstone',        goal: 1,  getProgress: ids          => ids.has('capstone') ? 1 : 0 },
]

function CoinSVG({ shape, size = 28, drop, style }) {
  const sw = Math.round(200 / size)
  const filter = drop ? `drop-shadow(${drop} var(--foreground))` : undefined
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" aria-hidden="true"
         style={{ display: 'block', flexShrink: 0, filter, ...style }}>
      {shape.id === 'circle'
        ? <circle cx="50" cy="50" r="44" fill="url(#coin-grad)" stroke="var(--foreground)" strokeWidth={sw}/>
        : <path d={shape.d} fill="url(#coin-grad)" stroke="var(--foreground)" strokeWidth={sw}/>}
    </svg>
  )
}

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
  const [purchased,  setPurchased]  = useState(getPurchased)
  const [active,     setActive]     = useState(getActive)
  const [spent,      setSpent]      = useState(getSpent)
  const [peakCoins,  setPeakCoins]  = useState(getPeakCoins)

  function refreshShop() {
    setPurchased(getPurchased())
    setActive(getActive())
    setSpent(getSpent())
    setPeakCoins(getPeakCoins())
  }

  useEffect(() => {
    if (!currentUser) { setCompletedIds(new Set()); return }
    supabase
      .from('lesson_progress')
      .select('lesson_id')
      .eq('user_id', currentUser.id)
      .eq('completed', true)
      .then(({ data }) => {
        if (data) setCompletedIds(new Set(data.map(r => r.lesson_id)))
      })
  }, [currentUser?.id])

  useEffect(() => {
    const refresh = () => refreshShop()
    window.addEventListener('incentive:shop-update', refresh)
    return () => window.removeEventListener('incentive:shop-update', refresh)
  }, [])

  useEffect(() => { applyCosmetics() }, [])

  const activeShape  = COIN_SHAPES.find(s => s.id !== 'circle' && active.has(s.id)) ?? COIN_SHAPES[0]
  const activeColor  = THEME_COLORS.find(c => active.has(c.id)) ?? null
  const earned       = profile?.xp ?? 0
  const coins        = Math.max(0, earned - spent)
  const xp           = earned * 2
  const lessonsCount = LESSON_IDS_ALL.filter(id => completedIds.has(id)).length
  const testsCount   = CHAPTER_TEST_IDS_ALL.filter(id => completedIds.has(id)).length

  useEffect(() => {
    const newPeak = updatePeakCoins(coins)
    if (newPeak > peakCoins) {
      setPeakCoins(newPeak)
      if (currentUser) saveShopToCloud(currentUser.id)
    }
  }, [coins])

  function openCertificate() {
    const name = profile?.name ?? currentUser?.email?.split('@')[0] ?? 'Student'
    const date = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
    const html = buildCertHtml({ name, lessonsCount, testsCount, coins, date })
    const win  = window.open('', '_blank', 'width=960,height=760')
    if (win) { win.document.write(html); win.document.close(); setTimeout(() => win.print(), 800) }
  }

  function handleBuy(itemId, price) {
    purchase(itemId, price)
    refreshShop()
    if (currentUser) saveShopToCloud(currentUser.id)
  }

  function handleEquip(itemId) {
    activateItem(itemId)
    setActive(getActive())
    if (currentUser) saveShopToCloud(currentUser.id)
  }

  function handleUnequipColor() {
    deactivateColor()
    setActive(getActive())
    if (currentUser) saveShopToCloud(currentUser.id)
  }

  function handleUnequipShape() {
    deactivateShape()
    setActive(getActive())
    if (currentUser) saveShopToCloud(currentUser.id)
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

        {/* Certificate */}
        {(() => {
          const capEarned = completedIds.has('capstone')
          return (
            <div className={`cert-achievement${capEarned ? ' cert-achievement--earned' : ''}`}>
              <div className={`cert-achievement-icon${capEarned ? ' cert-achievement-icon--earned' : ''}`}>
                {capEarned ? <Trophy size={28} strokeWidth={2.5} /> : <Lock size={24} strokeWidth={2.5} />}
              </div>
              <div className="cert-achievement-text">
                <span className="cert-achievement-label">Finance Certificate</span>
                <span className="cert-achievement-desc">
                  {capEarned
                    ? 'You completed the Capstone Challenge — your certificate is ready.'
                    : 'Complete the Capstone Challenge to earn your certificate of financial literacy.'}
                </span>
              </div>
              <button
                className={`btn ${capEarned ? 'btn-primary' : 'btn-secondary'} cert-achievement-btn`}
                disabled={!capEarned}
                onClick={capEarned ? openCertificate : undefined}
              >
                <span className="btn-label">{capEarned ? 'Download' : 'Locked'}</span>
                <span className="btn-icon-badge">
                  {capEarned ? <Download size={15} strokeWidth={2.5} /> : <Lock size={15} strokeWidth={2.5} />}
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
              {[...QUESTS]
                .map(q => {
                  const progress = q.getProgress(completedIds, coins, purchased, xp, peakCoins)
                  const done = progress >= q.goal
                  const pct  = Math.min((progress / q.goal) * 100, 100)
                  return { ...q, progress, done, pct }
                })
                .sort((a, b) => {
                  if (a.done !== b.done) return a.done ? 1 : -1
                  return b.pct - a.pct
                })
                .map(q => (
                  <div key={q.id} className={`quest-card${q.done ? ' quest-card--done' : ''}`}>
                    <div className="quest-card-top">
                      <div className={`quest-check${q.done ? ' quest-check--done' : ''}`}>
                        {q.done && <Check size={13} strokeWidth={3} />}
                      </div>
                      <div className="quest-card-text">
                        <span className="quest-card-label">{q.label}</span>
                        <span className="quest-card-desc">{q.desc}</span>
                      </div>
                      <span className="quest-card-count">{Math.min(q.progress, q.goal)}/{q.goal}</span>
                    </div>
                    <div className="quest-bar-track">
                      <div className="quest-bar-fill" style={{ width: `${Math.round(q.pct)}%` }} />
                    </div>
                  </div>
                ))
              }
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

            {/* Theme Colors */}
            <div className="shop-category">
              <div className="shop-cat-header">
                <span className="shop-cat-title">Theme Color</span>
                <span className="shop-cat-desc">Accents, buttons &amp; progress bars · 200¢ each</span>
              </div>
              <div className="shop-color-grid">
                {THEME_COLORS.map(color => {
                  const isFree   = color.price === 0
                  const owned    = isFree || purchased.has(color.id)
                  const isActive = active.has(color.id)
                  const canBuy   = !owned && coins >= color.price
                  return (
                    <div key={color.id} className={`shop-color-item${isActive ? ' shop-color-item--active' : ''}`}>
                      <div className="shop-color-swatch" style={{ background: color.hex }}>
                        {isActive && <Check size={18} strokeWidth={3} color="white" />}
                      </div>
                      <div className="shop-color-footer">
                        <span className="shop-color-name">{color.label}</span>
                        {owned ? (
                          <button
                            className={`btn ${isActive ? 'btn-secondary' : 'btn-primary'} shop-pill-btn`}
                            onClick={() => isActive ? handleUnequipColor() : handleEquip(color.id)}
                          >
                            {isActive ? 'On' : 'Use'}
                          </button>
                        ) : (
                          <button
                            className={`btn ${canBuy ? 'btn-primary' : 'btn-secondary'} shop-pill-btn`}
                            disabled={!canBuy}
                            onClick={() => canBuy && handleBuy(color.id, color.price)}
                          >
                            {color.price}¢
                          </button>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Coin Shapes */}
            <div className="shop-category">
              <div className="shop-cat-header">
                <span className="shop-cat-title">Coin Shape</span>
                <span className="shop-cat-desc">Changes every coin badge on the site</span>
              </div>
              <div className="shop-shape-grid">
                {COIN_SHAPES.map(shape => {
                  const isFree   = shape.price === 0
                  const owned    = isFree || purchased.has(shape.id)
                  const isActive = isFree
                    ? !COIN_SHAPES.some(s => s.id !== 'circle' && active.has(s.id))
                    : active.has(shape.id)
                  const canBuy   = !owned && coins >= shape.price
                  return (
                    <div key={shape.id} className={`shop-shape-item${isActive ? ' shop-shape-item--active' : ''}${!owned ? ' shop-shape-item--locked' : ''}`}>
                      <div className="shop-shape-preview">
                        <CoinSVG shape={shape} size={46} drop="2px 2px 0"
                          style={{ opacity: owned ? 1 : 0.45 }}
                        />
                        {!owned && (
                          <div className="shop-shape-lock-badge">
                            <Lock size={10} strokeWidth={2.5} />
                          </div>
                        )}
                        {isActive && (
                          <div className="shop-shape-active-badge">
                            <Check size={10} strokeWidth={3} />
                          </div>
                        )}
                      </div>
                      <span className="shop-shape-name">{shape.label}</span>
                      {isFree ? (
                        <button
                          className={`btn ${isActive ? 'btn-secondary' : 'btn-primary'} shop-pill-btn`}
                          disabled={isActive}
                          onClick={() => !isActive && handleEquip('circle')}
                        >
                          {isActive ? 'On' : 'Use'}
                        </button>
                      ) : owned ? (
                        <button
                          className={`btn ${isActive ? 'btn-secondary' : 'btn-primary'} shop-pill-btn`}
                          onClick={() => isActive ? handleUnequipShape() : handleEquip(shape.id)}
                        >
                          {isActive ? 'On' : 'Use'}
                        </button>
                      ) : (
                        <button
                          className={`btn ${canBuy ? 'btn-primary' : 'btn-secondary'} shop-pill-btn`}
                          disabled={!canBuy}
                          onClick={() => canBuy && handleBuy(shape.id, shape.price)}
                        >
                          {shape.price}¢
                        </button>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>

          </section>

        </div>
      </div>
    </main>
  )
}
