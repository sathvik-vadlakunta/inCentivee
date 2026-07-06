import { createContext, useContext, useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [currentUser, setCurrentUser] = useState(null)
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)

  async function fetchProfile(userId) {
    const { data } = await supabase.from('profiles').select('*').eq('id', userId).single()
    // Merge with existing state so locally-computed xp isn't overwritten
    // if the DB profile doesn't have that column
    setProfile(prev => data ? { xp: 0, ...prev, ...data } : prev)
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
      else setProfile(null)
    })

    return () => subscription.unsubscribe()
  }, [])

  async function signUp(name, email, password) {
    const { data, error } = await supabase.auth.signUp({ email, password })
    if (error) throw error
    if (!data.session) {
      // Email confirmation is required — inform the user
      throw new Error('CHECK_EMAIL')
    }
    // Upsert so re-signups don't duplicate rows
    await supabase.from('profiles').upsert({ id: data.user.id, name }, { onConflict: 'id' })
    await fetchProfile(data.user.id)
  }

  async function logIn(email, password) {
    const { data, error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) throw error
    // Create profile if it doesn't exist yet (e.g. confirmed email after signup)
    if (data.user) {
      const { data: existing } = await supabase.from('profiles').select('id').eq('id', data.user.id).single()
      if (!existing) {
        await supabase.from('profiles').insert({ id: data.user.id, name: data.user.email.split('@')[0] })
      }
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
