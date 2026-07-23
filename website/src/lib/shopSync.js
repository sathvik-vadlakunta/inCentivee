import { supabase } from './supabase'
import { getPurchased, getActive, getSpent, getPeakCoins, applyCosmetics } from './shop'

const PURCHASED_KEY = 'incentive_shop_purchased'
const ACTIVE_KEY    = 'incentive_shop_active'
const SPENT_KEY     = 'incentive_shop_spent'
const PEAK_KEY      = 'incentive_peak_coins'

export async function loadShopFromCloud(userId) {
  const { data } = await supabase
    .from('user_shop')
    .select('purchased, active, spent, peak_coins')
    .eq('user_id', userId)
    .single()

  if (!data) return

  localStorage.setItem(PURCHASED_KEY, JSON.stringify(data.purchased  ?? []))
  localStorage.setItem(ACTIVE_KEY,    JSON.stringify(data.active     ?? []))
  localStorage.setItem(SPENT_KEY,     String(data.spent              ?? 0))
  localStorage.setItem(PEAK_KEY,      String(data.peak_coins         ?? 0))
  applyCosmetics()
  window.dispatchEvent(new CustomEvent('incentive:shop-update'))
}

export async function saveShopToCloud(userId) {
  if (!userId) return
  await supabase.from('user_shop').upsert({
    user_id:    userId,
    purchased:  [...getPurchased()],
    active:     [...getActive()],
    spent:      getSpent(),
    peak_coins: getPeakCoins(),
  }, { onConflict: 'user_id' })
}
