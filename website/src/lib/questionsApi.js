import { supabase } from './supabase'

// Fetches every question row and reshapes it into the two forms the app needs:
//   byLesson[lessonId]  -> ordered array of multiple-choice questions
//   fillBlanks[unitId]  -> single fill-blank question object (or undefined)
export async function fetchQuestionsMap() {
  const { data, error } = await supabase
    .from('questions')
    .select('*')
    .order('position', { ascending: true })

  if (error) throw error

  const byLesson = {}
  const fillBlanks = {}

  for (const row of data ?? []) {
    const q = {
      id: row.id,
      prompt: row.prompt,
      options: row.options,
      correct: row.correct,
      explanation: row.explanation,
    }
    if (row.type === 'fill-blank') {
      q.type = 'fill-blank'
      fillBlanks[row.unit_id] = q
    } else if (row.lesson_id) {
      if (!byLesson[row.lesson_id]) byLesson[row.lesson_id] = []
      byLesson[row.lesson_id].push(q)
    }
  }

  return { byLesson, fillBlanks }
}

export async function fetchQuestionsForLesson(lessonId) {
  const { data, error } = await supabase
    .from('questions')
    .select('*')
    .eq('lesson_id', lessonId)
    .eq('type', 'multiple-choice')
    .order('position', { ascending: true })
  if (error) throw error
  return data ?? []
}

export async function fetchFillBlank(unitId) {
  const { data, error } = await supabase
    .from('questions')
    .select('*')
    .eq('unit_id', unitId)
    .eq('type', 'fill-blank')
    .maybeSingle()
  if (error) throw error
  return data
}

export async function createQuestion({ unitId, lessonId, type = 'multiple-choice', position = 0, prompt, options, correct, explanation }) {
  const { data, error } = await supabase
    .from('questions')
    .insert({ unit_id: unitId, lesson_id: lessonId ?? null, type, position, prompt, options, correct, explanation })
    .select()
    .single()
  if (error) throw error
  return data
}

export async function updateQuestion(id, patch) {
  const { data, error } = await supabase
    .from('questions')
    .update(patch)
    .eq('id', id)
    .select()
    .single()
  if (error) throw error
  return data
}

export async function deleteQuestion(id) {
  const { error } = await supabase.from('questions').delete().eq('id', id)
  if (error) throw error
}

// Fill-blank is one row per unit — upsert by first checking if one exists.
export async function upsertFillBlank(unitId, { prompt, options, correct, explanation }) {
  const existing = await fetchFillBlank(unitId)
  if (existing) {
    return updateQuestion(existing.id, { prompt, options, correct, explanation })
  }
  return createQuestion({ unitId, lessonId: null, type: 'fill-blank', position: 0, prompt, options, correct, explanation })
}

export async function deleteFillBlank(unitId) {
  const existing = await fetchFillBlank(unitId)
  if (existing) await deleteQuestion(existing.id)
}
