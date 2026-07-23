import { supabase } from './supabase'
import { getPurchased, getActive, getSpent, applyCosmetics } from './shop'

const PURCHASED_KEY = 'incentive_shop_purchased'
const ACTIVE_KEY    = 'incentive_shop_active'
const SPENT_KEY     = 'incentive_shop_spent'

export async function loadShopFromCloud(userId) {
  const { data } = await supabase
    .from('user_shop')
    .select('purchased, active, spent')
    .eq('user_id', userId)
    .single()

  if (!data) return

  localStorage.setItem(PURCHASED_KEY, JSON.stringify(data.purchased ?? []))
  localStorage.setItem(ACTIVE_KEY,    JSON.stringify(data.active    ?? []))
  localStorage.setItem(SPENT_KEY,     String(data.spent ?? 0))
  applyCosmetics()
  window.dispatchEvent(new CustomEvent('incentive:shop-update'))
}

export async function saveShopToCloud(userId) {
  if (!userId) return
  await supabase.from('user_shop').upsert({
    user_id:   userId,
    purchased: [...getPurchased()],
    active:    [...getActive()],
    spent:     getSpent(),
  }, { onConflict: 'user_id' })
}
