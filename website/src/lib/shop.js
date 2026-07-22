const PURCHASED_KEY = 'incentive_shop_purchased'
const ACTIVE_KEY    = 'incentive_shop_active'
const SPENT_KEY     = 'incentive_shop_spent'

const COIN_SHAPE_CLASSES = ['shop-coin-star','shop-coin-hexagon','shop-coin-diamond','shop-coin-shield']

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

export function getCustomValue(key, fallback = '') {
  return localStorage.getItem(`incentive_custom_${key}`) ?? fallback
}

export function setCustomValue(key, value) {
  localStorage.setItem(`incentive_custom_${key}`, value)
  applyCosmetics()
}

export function purchase(itemId, price) {
  const purchased = getPurchased()
  if (purchased.has(itemId)) return
  purchased.add(itemId)
  localStorage.setItem(PURCHASED_KEY, JSON.stringify([...purchased]))
  localStorage.setItem(SPENT_KEY, String(getSpent() + price))
  toggleItem(itemId, true)
}

export function toggleItem(itemId, on) {
  const active = getActive()
  if (on) active.add(itemId)
  else    active.delete(itemId)
  localStorage.setItem(ACTIVE_KEY, JSON.stringify([...active]))
  applyCosmetics(active)
}

export function applyCosmetics(active) {
  if (!active) active = getActive()
  const root = document.documentElement
  const body = document.body

  // Accent color
  if (active.has('custom-accent')) {
    root.style.setProperty('--accent', getCustomValue('accent', '#FF6F61'))
  } else {
    root.style.removeProperty('--accent')
  }

  // Navbar color
  if (active.has('custom-nav')) {
    root.style.setProperty('--navbar-custom-bg', getCustomValue('nav', '#1E293B'))
    body.classList.add('shop-custom-nav')
  } else {
    root.style.removeProperty('--navbar-custom-bg')
    body.classList.remove('shop-custom-nav')
  }

  // Coin shape
  COIN_SHAPE_CLASSES.forEach(c => body.classList.remove(c))
  if (active.has('custom-coin')) {
    const shape = getCustomValue('coin_shape', 'circle')
    if (shape !== 'circle') body.classList.add(`shop-coin-${shape}`)
  }
  window.dispatchEvent(new CustomEvent('incentive:coin-shape'))

  // Progress bar color
  if (active.has('custom-progress')) {
    root.style.setProperty('--progress-custom-color', getCustomValue('progress', '#F59E0B'))
    body.classList.add('shop-custom-progress')
  } else {
    root.style.removeProperty('--progress-custom-color')
    body.classList.remove('shop-custom-progress')
  }
}
