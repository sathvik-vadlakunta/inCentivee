import { createContext, useContext, useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'
import { allUnits } from '../data/levels'
import { clearStoredProgress } from '../lib/guestProgress'
import { clearShopData } from '../lib/shop'
import { loadShopFromCloud } from '../lib/shopSync'

const AuthContext = createContext(null)

// Build a flat id→centsReward map covering units AND individual lessons
const rewardMap = {}
allUnits.forEach(u => {
  rewardMap[u.id] = u.centsReward ?? 0
  if (u.lessons) u.lessons.forEach(l => { rewardMap[l.id] = l.centsReward ?? 0 })
})

function computeXP(rows) {
  let total = 0
  rows.forEach(r => {
    const pct = (r.score ?? 0) / 100
    if (rewardMap[r.lesson_id] !== undefined) {
      total += Math.round(rewardMap[r.lesson_id] * pct)
    } else if (r.lesson_id === 'capstone') {
      total += Math.round(200 * pct)
    } else if (r.lesson_id.endsWith('-test')) {
      total += Math.round(100 * pct)
    }
  })
  return total
}

export function AuthProvider({ children }) {
  const [currentUser, setCurrentUser] = useState(null)
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)

  async function fetchProfile(userId) {
    const [{ data: profileData }, { data: progressData }] = await Promise.all([
      supabase.from('profiles').select('*').eq('id', userId).single(),
      supabase.from('lesson_progress').select('lesson_id, score').eq('user_id', userId).eq('completed', true),
    ])
    const xp = progressData ? computeXP(progressData) : 0
    setProfile(prev => ({ ...prev, ...(profileData ?? {}), xp }))
    loadShopFromCloud(userId)
  }

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setCurrentUser(session?.user ?? null)
      if (session?.user) fetchProfile(session.user.id)
      setLoading(false)
    })

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setCurrentUser(session?.user ?? null)
      if (session?.user) fetchProfile(session.user.id)
      else { setProfile(null); clearStoredProgress(); clearShopData() }
    })

    return () => subscription.unsubscribe()
  }, [])

  async function signUp(name, email, password) {
    const { data, error } = await supabase.auth.signUp({ email, password })
    if (error) throw error
    if (!data.session) throw new Error('CHECK_EMAIL')
    await supabase.from('profiles').upsert({ id: data.user.id, name }, { onConflict: 'id' })
    await fetchProfile(data.user.id)
  }

  async function logIn(email, password) {
    const { data, error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) throw error
    if (data.user) {
      const { data: existing } = await supabase.from('profiles').select('id').eq('id', data.user.id).single()
      if (!existing) {
        await supabase.from('profiles').insert({ id: data.user.id, name: data.user.email.split('@')[0] })
      }
      setCurrentUser(data.user)
      await fetchProfile(data.user.id)
    }
  }

  async function logOut() {
    await supabase.auth.signOut()
  }

  async function refreshProfile() {
    if (currentUser) await fetchProfile(currentUser.id)
  }

  function bumpXP(amount) {
    setProfile(prev => prev ? { ...prev, xp: (prev.xp ?? 0) + amount } : { xp: amount })
  }

  function setXP(amount) {
    setProfile(prev => prev ? { ...prev, xp: amount } : { xp: amount })
  }

  return (
    <AuthContext.Provider value={{ currentUser, profile, loading, signUp, logIn, logOut, refreshProfile, bumpXP, setXP }}>
      {!loading && children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
