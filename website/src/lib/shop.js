const PURCHASED_KEY = 'incentive_shop_purchased'
const ACTIVE_KEY    = 'incentive_shop_active'
const SPENT_KEY     = 'incentive_shop_spent'
const PEAK_KEY      = 'incentive_peak_coins'

export const THEME_COLORS = [
  { id: 'color-coral',  hex: '#FF6F61', label: 'Coral',  price: 0 },
  { id: 'color-teal',   hex: '#0D9488', label: 'Teal',   price: 200 },
  { id: 'color-amber',  hex: '#F59E0B', label: 'Amber',  price: 200 },
  { id: 'color-purple', hex: '#8B5CF6', label: 'Purple', price: 200 },
  { id: 'color-blue',   hex: '#3B82F6', label: 'Blue',   price: 200 },
  { id: 'color-pink',   hex: '#EC4899', label: 'Pink',   price: 200 },
]

export const COIN_SHAPES = [
  { id: 'circle',  label: 'Circle',  price: 0,    d: null },
  { id: 'star',    label: 'Star',    price: 200,  d: 'M44.2,11.5 Q50,3 55.8,11.5 L66.5,27.4 L84.8,32.7 Q94.7,35.5 88.4,43.6 L76.6,58.7 L77.2,77.8 Q77.6,88 67.9,84.5 L50,78 L32.1,84.5 Q22.4,88 22.8,77.8 L23.4,58.7 L11.6,43.6 Q5.3,35.5 15.2,32.7 L33.5,27.4 Z' },
  { id: 'hexagon', label: 'Hexagon', price: 400,  d: 'M43.9,6.5 Q50,3 56.1,6.5 L84.6,23 Q90.7,26.5 90.7,33.5 L90.7,66.5 Q90.7,73.5 84.6,77 L56.1,93.5 Q50,97 43.9,93.5 L15.4,77 Q9.3,73.5 9.3,66.5 L9.3,33.5 Q9.3,26.5 15.4,23 Z' },
  { id: 'diamond', label: 'Diamond', price: 800,  d: 'M41.5,11.5 Q50,3 58.5,11.5 L88.5,41.5 Q97,50 88.5,58.5 L58.5,88.5 Q50,97 41.5,88.5 L11.5,58.5 Q3,50 11.5,41.5 Z' },
  { id: 'shield',  label: 'Shield',  price: 1600, d: 'M12,10 Q50,5 88,10 C96,15 97,40 90,65 C82,82 65,93 50,97 C35,93 18,82 10,65 C3,40 4,15 12,10 Z' },
  { id: 'gem',     label: 'Gem',     price: 3200, d: 'M90,34 L67,10 L33,10 L10,34 L10,66 L33,90 L67,90 L90,66 Z' },
]

export function getPurchased() {
  try { return new Set(JSON.parse(localStorage.getItem(PURCHASED_KEY) ?? '[]')) }
  catch { return new Set() }
}

export function getActive() {
  try { return new Set(JSON.parse(localStorage.getItem(ACTIVE_KEY) ?? '[]')) }
  catch { return new Set() }
}

export function getSpent() {
  return parseInt(localStorage.getItem(SPENT_KEY) ?? '0', 10)
}

export function getPeakCoins() {
  return parseInt(localStorage.getItem(PEAK_KEY) ?? '0', 10)
}

export function updatePeakCoins(current) {
  const peak = getPeakCoins()
  if (current > peak) {
    localStorage.setItem(PEAK_KEY, String(current))
    return current
  }
  return peak
}

export function purchase(itemId, price) {
  const purchased = getPurchased()
  if (purchased.has(itemId)) return
  purchased.add(itemId)
  localStorage.setItem(PURCHASED_KEY, JSON.stringify([...purchased]))
  localStorage.setItem(SPENT_KEY, String(getSpent() + price))
  activateItem(itemId)
  window.dispatchEvent(new CustomEvent('incentive:shop-update'))
}

export function activateItem(itemId) {
  const active = getActive()
  if (itemId.startsWith('color-')) {
    THEME_COLORS.forEach(c => active.delete(c.id))
    active.add(itemId)
  } else {
    COIN_SHAPES.forEach(s => { if (s.id !== 'circle') active.delete(s.id) })
    if (itemId !== 'circle') active.add(itemId)
  }
  localStorage.setItem(ACTIVE_KEY, JSON.stringify([...active]))
  applyCosmetics(active)
}

export function deactivateColor() {
  const active = getActive()
  THEME_COLORS.forEach(c => active.delete(c.id))
  localStorage.setItem(ACTIVE_KEY, JSON.stringify([...active]))
  applyCosmetics(active)
}

export function deactivateShape() {
  const active = getActive()
  COIN_SHAPES.forEach(s => { if (s.id !== 'circle') active.delete(s.id) })
  localStorage.setItem(ACTIVE_KEY, JSON.stringify([...active]))
  applyCosmetics(active)
}

export function clearShopData() {
  try {
    localStorage.removeItem(PURCHASED_KEY)
    localStorage.removeItem(ACTIVE_KEY)
    localStorage.removeItem(SPENT_KEY)
    localStorage.removeItem(PEAK_KEY)
  } catch {}
  applyCosmetics(new Set())
  window.dispatchEvent(new CustomEvent('incentive:shop-update'))
}

export function applyCosmetics(active) {
  if (!active) active = getActive()
  const root = document.documentElement

  const activeColor = THEME_COLORS.find(c => active.has(c.id))
  if (activeColor) {
    root.style.setProperty('--accent', activeColor.hex)
  } else {
    root.style.removeProperty('--accent')
  }

  window.dispatchEvent(new CustomEvent('incentive:coin-shape'))
}
