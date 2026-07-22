import { useState, useEffect } from 'react'
import { getActive, COIN_SHAPES } from '../lib/shop'

function resolveShape() {
  const active = getActive()
  return COIN_SHAPES.find(s => s.id !== 'circle' && active.has(s.id)) ?? COIN_SHAPES[0]
}

export default function CoinBadge({ size = 24, drop = '1px 1px 0', style }) {
  const [shape, setShape] = useState(resolveShape)

  useEffect(() => {
    const upd = () => setShape(resolveShape())
    window.addEventListener('incentive:coin-shape', upd)
    return () => window.removeEventListener('incentive:coin-shape', upd)
  }, [])

  const sw = Math.round(200 / size)

  return (
    <svg
      width={size} height={size} viewBox="0 0 100 100"
      aria-hidden="true"
      style={{ display: 'block', flexShrink: 0, filter: `drop-shadow(${drop} var(--foreground))`, ...style }}
    >
      {shape.id === 'circle'
        ? <circle cx="50" cy="50" r="44" fill="url(#coin-grad)" stroke="var(--foreground)" strokeWidth={sw}/>
        : <path d={shape.d} fill="url(#coin-grad)" stroke="var(--foreground)" strokeWidth={sw}/>}
    </svg>
  )
}
