// One-time migration: pushes scripts/questions-seed.json into the `questions` table.
//
// Before running this:
//   1. Run scripts/schema.sql once in the Supabase SQL Editor.
//   2. Make sure you have an account on the live site (sign up at /login) using
//      incentivefinanceinfo@gmail.com — the same email schema.sql allow-listed for writes.
//
// Run with:  node scripts/migrate-questions.mjs
// It will prompt for your email + password, sign in, then bulk-insert all
// existing questions. Safe to re-run — it clears out its own rows first so you
// never end up with duplicates.

import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'
import { createClient } from '@supabase/supabase-js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(__dirname, '..')

function loadEnvLocal() {
  const envPath = path.join(root, '.env.local')
  const text = fs.readFileSync(envPath, 'utf8')
  const env = {}
  for (const line of text.split('\n')) {
    const trimmed = line.trim()
    if (!trimmed || trimmed.startsWith('#')) continue
    const eq = trimmed.indexOf('=')
    if (eq === -1) continue
    env[trimmed.slice(0, eq).trim()] = trimmed.slice(eq + 1).trim()
  }
  return env
}

function askVisible(question) {
  return new Promise((resolve) => {
    const rl = readline.createInterface({ input: process.stdin, output: process.stdout })
    rl.question(question, (answer) => { rl.close(); resolve(answer) })
  })
}

// Masked password prompt using raw stdin. Falls back to visible input if the
// terminal doesn't support raw mode (e.g. some non-interactive shells).
function askPassword(question) {
  return new Promise((resolve) => {
    const stdin = process.stdin
    if (!stdin.isTTY || typeof stdin.setRawMode !== 'function') {
      resolve(askVisible(question))
      return
    }
    process.stdout.write(question)
    let value = ''
    stdin.setRawMode(true)
    stdin.resume()
    stdin.setEncoding('utf8')

    const CODE_ENTER = [10, 13]        // \n, \r
    const CODE_CTRL_C = 3
    const CODE_BACKSPACE = [8, 127]    // \b, DEL

    function cleanup() {
      stdin.setRawMode(false)
      stdin.pause()
      stdin.removeListener('data', onData)
    }

    function onData(chunk) {
      const code = chunk.charCodeAt(0)
      if (CODE_ENTER.includes(code)) {
        cleanup()
        process.stdout.write('\n')
        resolve(value)
      } else if (code === CODE_CTRL_C) {
        cleanup()
        process.stdout.write('\n')
        process.exit(1)
      } else if (CODE_BACKSPACE.includes(code)) {
        value = value.slice(0, -1)
      } else {
        value += chunk
      }
    }

    stdin.on('data', onData)
  })
}

async function main() {
  const env = loadEnvLocal()
  const SUPABASE_URL = env.VITE_SUPABASE_URL
  const SERVICE_KEY  = env.SUPABASE_SERVICE_KEY
  if (!SUPABASE_URL || !SERVICE_KEY) {
    console.error('Missing VITE_SUPABASE_URL or SUPABASE_SERVICE_KEY in .env.local')
    console.error('Get your service_role key from Supabase → Project Settings → API')
    process.exit(1)
  }

  const supabase = createClient(SUPABASE_URL, SERVICE_KEY, {
    auth: { autoRefreshToken: false, persistSession: false },
  })
  console.log('Connected with service role key — bypassing RLS')

  const seedPath = path.join(__dirname, 'questions-seed.json')
  const rows = JSON.parse(fs.readFileSync(seedPath, 'utf8'))
  console.log(`Loaded ${rows.length} questions from seed file.`)

  console.log('Clearing any previously-migrated rows (safe if table is already empty)...')
  await supabase.from('questions').delete().gte('id', 0)

  const BATCH_SIZE = 500
  let inserted = 0
  for (let i = 0; i < rows.length; i += BATCH_SIZE) {
    const batch = rows.slice(i, i + BATCH_SIZE)
    const { error } = await supabase.from('questions').insert(batch)
    if (error) {
      console.error(`Batch starting at row ${i} failed:`, error.message)
      process.exit(1)
    }
    inserted += batch.length
    console.log(`Inserted ${inserted} / ${rows.length}`)
  }

  console.log('Done. Your questions now live in Supabase.')
  process.exit(0)
}

main()
