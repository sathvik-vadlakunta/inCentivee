const KEY = 'incentive_lesson_progress'

export function getStoredProgress() {
  try {
    return new Set(JSON.parse(localStorage.getItem(KEY) || '[]'))
  } catch {
    return new Set()
  }
}

export function storeProgress(ids) {
  try {
    localStorage.setItem(KEY, JSON.stringify([...ids]))
  } catch {}
}

export function clearStoredProgress() {
  try {
    localStorage.removeItem(KEY)
  } catch {}
}
