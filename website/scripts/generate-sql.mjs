// Reads questions-seed.json and writes insert.sql
// Run: node scripts/generate-sql.mjs
// Then paste insert.sql into Supabase SQL Editor and click Run.

import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const rows = JSON.parse(fs.readFileSync(path.join(__dirname, 'questions-seed.json'), 'utf8'))

const esc = str => (str ?? '').replace(/'/g, "''")

const values = rows.map(r => {
  const unitId   = r.unit_id   ? `'${esc(r.unit_id)}'`   : 'NULL'
  const lessonId = r.lesson_id ? `'${esc(r.lesson_id)}'` : 'NULL'
  const options  = `'${esc(JSON.stringify(r.options))}'::jsonb`
  return `(gen_random_uuid(), ${unitId}, ${lessonId}, '${esc(r.type)}', ${r.position}, '${esc(r.prompt)}', ${options}, ${r.correct}, '${esc(r.explanation ?? '')}')`
}).join(',\n')

const sql = `-- Auto-generated — paste into Supabase SQL Editor and click Run
TRUNCATE TABLE questions;

INSERT INTO questions (id, unit_id, lesson_id, type, position, prompt, options, correct, explanation)
VALUES
${values};
`

const outPath = path.join(__dirname, 'insert.sql')
fs.writeFileSync(outPath, sql)
console.log(`Done — ${rows.length} rows written to scripts/insert.sql`)
console.log('Paste that file into your Supabase SQL Editor and click Run.')
