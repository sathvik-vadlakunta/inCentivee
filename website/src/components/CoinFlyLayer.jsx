import { useEffect, useState } from 'react'
import './CoinFly.css'

let _id = 0

export function triggerCoinFly(amount) {
  if (!amount || amount <= 0) return
  const count = Math.min(amount, 20)
  window.dispatchEvent(new CustomEvent('coinfly', { detail: { count, type: 'coin' } }))
}

export function triggerXPFly(amount) {
  if (!amount || amount <= 0) return
  const count = Math.min(amount, 20)
  window.dispatchEvent(new CustomEvent('coinfly', { detail: { count, type: 'xp' } }))
}

export default function CoinFlyLayer() {
  const [coins, setCoins] = useState([])

  useEffect(() => {
    function onCoinFly(e) {
      const { count, type } = e.detail

      const targetEl = type === 'xp'
        ? (document.querySelector('.navbar-actions .navbar-xp') ?? document.querySelector('.navbar-xp--mobile'))
        : (document.querySelector('.navbar-actions .navbar-cents') ?? document.querySelector('.navbar-cents--mobile'))
      if (!targetEl) return

      const rect = targetEl.getBoundingClientRect()
      const tx = rect.left + rect.width / 2
      const ty = rect.top  + rect.height / 2

      const cx = window.innerWidth  / 2
      const cy = window.innerHeight / 2

      const batch = Array.from({ length: count }, (_, i) => ({
        id: ++_id,
        sx: cx + (Math.random() - 0.5) * 100,
        sy: cy + (Math.random() - 0.5) * 80,
        tx,
        ty,
        delay: i * 65,
        type,
      }))

      setCoins(prev => [...prev, ...batch])
    }

    window.addEventListener('coinfly', onCoinFly)
    return () => window.removeEventListener('coinfly', onCoinFly)
  }, [])

  return (
    <div className="coin-fly-layer" aria-hidden="true">
      {coins.map(c => (
        <div
          key={c.id}
          className={`coin-fly coin-fly--${c.type}`}
          style={{
            left: c.sx,
            top:  c.sy,
            '--tx': `${c.tx - c.sx}px`,
            '--ty': `${c.ty - c.sy}px`,
            animationDelay: `${c.delay}ms`,
          }}
          onAnimationEnd={() => setCoins(prev => prev.filter(x => x.id !== c.id))}
        >
          {c.type === 'xp' ? '⚡' : '¢'}
        </div>
      ))}
    </div>
  )
}
