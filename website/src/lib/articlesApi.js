import { supabase } from './supabase'

export async function fetchArticles() {
  const { data, error } = await supabase
    .from('articles')
    .select('*')
    .order('published_at', { ascending: false })
  if (error) throw error
  return data ?? []
}

export async function fetchArticle(id) {
  const { data, error } = await supabase
    .from('articles')
    .select('*')
    .eq('id', id)
    .single()
  if (error) throw error
  return data
}

export async function createArticle({ title, body, author }) {
  const { data, error } = await supabase
    .from('articles')
    .insert({ title, body, author, published_at: new Date().toISOString() })
    .select()
    .single()
  if (error) throw error
  return data
}

export async function updateArticle(id, patch) {
  const { data, error } = await supabase
    .from('articles')
    .update(patch)
    .eq('id', id)
    .select()
    .single()
  if (error) throw error
  return data
}

export async function deleteArticle(id) {
  const { error } = await supabase.from('articles').delete().eq('id', id)
  if (error) throw error
}
