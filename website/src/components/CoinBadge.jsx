import { useState, useEffect } from 'react'
import { getActive, getCustomValue } from '../lib/shop'

const SHAPES = [
  { id: 'circle',  d: null },
  { id: 'star',    d: 'M44.2,11.5 Q50,3 55.8,11.5 L66.5,27.4 L84.8,32.7 Q94.7,35.5 88.4,43.6 L76.6,58.7 L77.2,77.8 Q77.6,88 67.9,84.5 L50,78 L32.1,84.5 Q22.4,88 22.8,77.8 L23.4,58.7 L11.6,43.6 Q5.3,35.5 15.2,32.7 L33.5,27.4 Z' },
  { id: 'hexagon', d: 'M43.9,6.5 Q50,3 56.1,6.5 L84.6,23 Q90.7,26.5 90.7,33.5 L90.7,66.5 Q90.7,73.5 84.6,77 L56.1,93.5 Q50,97 43.9,93.5 L15.4,77 Q9.3,73.5 9.3,66.5 L9.3,33.5 Q9.3,26.5 15.4,23 Z' },
  { id: 'diamond', d: 'M41.5,11.5 Q50,3 58.5,11.5 L88.5,41.5 Q97,50 88.5,58.5 L58.5,88.5 Q50,97 41.5,88.5 L11.5,58.5 Q3,50 11.5,41.5 Z' },
  { id: 'shield',  d: 'M12,10 Q50,5 88,10 C96,15 97,40 90,65 C82,82 65,93 50,97 C35,93 18,82 10,65 C3,40 4,15 12,10 Z' },
]

function resolveShape() {
  const active = getActive()
  const id = active.has('custom-coin') ? getCustomValue('coin_shape', 'circle') : 'circle'
  return SHAPES.find(s => s.id === id) ?? SHAPES[0]
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
