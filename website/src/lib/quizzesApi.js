import { supabase } from './supabase'

function randomCode() {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
  return Array.from({ length: 6 }, () => chars[Math.floor(Math.random() * chars.length)]).join('')
}

export async function fetchQuizByCode(code) {
  const { data, error } = await supabase
    .from('quizzes')
    .select('*, quiz_questions(*)')
    .eq('code', code.toUpperCase())
    .single()
  if (error) throw error
  data.quiz_questions.sort((a, b) => a.position - b.position)
  return data
}

export async function fetchMyQuizzes(userId) {
  const { data, error } = await supabase
    .from('quizzes')
    .select('id, title, code, created_at')
    .eq('user_id', userId)
    .order('created_at', { ascending: false })
  if (error) throw error
  return data ?? []
}

export async function fetchQuizById(id) {
  const { data, error } = await supabase
    .from('quizzes')
    .select('*, quiz_questions(*)')
    .eq('id', id)
    .single()
  if (error) throw error
  data.quiz_questions.sort((a, b) => a.position - b.position)
  return data
}

export async function createQuiz(userId, title, questions) {
  let code, attempts = 0
  while (attempts < 10) {
    code = randomCode()
    const { data } = await supabase.from('quizzes').select('id').eq('code', code).maybeSingle()
    if (!data) break
    attempts++
  }
  const { data: quiz, error } = await supabase
    .from('quizzes')
    .insert({ user_id: userId, title, code })
    .select()
    .single()
  if (error) throw error

  if (questions.length > 0) {
    const rows = questions.map((q, i) => ({
      quiz_id: quiz.id, prompt: q.prompt, options: q.options,
      correct: q.correct, explanation: q.explanation ?? '', position: i,
    }))
    const { error: qErr } = await supabase.from('quiz_questions').insert(rows)
    if (qErr) throw qErr
  }
  return quiz
}

export async function updateQuiz(quizId, title, questions) {
  const { error } = await supabase.from('quizzes').update({ title }).eq('id', quizId)
  if (error) throw error

  await supabase.from('quiz_questions').delete().eq('quiz_id', quizId)
  if (questions.length > 0) {
    const rows = questions.map((q, i) => ({
      quiz_id: quizId, prompt: q.prompt, options: q.options,
      correct: q.correct, explanation: q.explanation ?? '', position: i,
    }))
    const { error: qErr } = await supabase.from('quiz_questions').insert(rows)
    if (qErr) throw qErr
  }
}

export async function deleteQuiz(id) {
  const { error } = await supabase.from('quizzes').delete().eq('id', id)
  if (error) throw error
}
