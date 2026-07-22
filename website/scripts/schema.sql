-- Run this once in the Supabase SQL Editor (Project -> SQL Editor -> New query).
-- Creates the questions table that will hold all lesson + fill-blank content,
-- and locks writes down to your admin account only.

create table if not exists public.questions (
  id bigint generated always as identity primary key,
  unit_id text not null,
  lesson_id text,                 -- null for fill-blank (unit-level) questions
  type text not null default 'multiple-choice' check (type in ('multiple-choice', 'fill-blank')),
  position integer not null default 0,
  prompt text not null,
  options jsonb not null,
  correct integer not null,
  explanation text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists questions_lesson_id_idx on public.questions (lesson_id);
create index if not exists questions_unit_id_idx on public.questions (unit_id);

-- keep updated_at fresh on edit
create or replace function public.set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists questions_set_updated_at on public.questions;
create trigger questions_set_updated_at
  before update on public.questions
  for each row execute function public.set_updated_at();

-- Row Level Security: anyone can read (the live site needs this to show questions
-- to logged-out visitors too), but only your admin account can write.
alter table public.questions enable row level security;

drop policy if exists "questions are publicly readable" on public.questions;
create policy "questions are publicly readable"
  on public.questions for select
  using (true);

drop policy if exists "only admin can insert questions" on public.questions;
create policy "only admin can insert questions"
  on public.questions for insert
  with check ((auth.jwt() ->> 'email') = 'incentivefinanceinfo@gmail.com');

drop policy if exists "only admin can update questions" on public.questions;
create policy "only admin can update questions"
  on public.questions for update
  using ((auth.jwt() ->> 'email') = 'incentivefinanceinfo@gmail.com')
  with check ((auth.jwt() ->> 'email') = 'incentivefinanceinfo@gmail.com');

drop policy if exists "only admin can delete questions" on public.questions;
create policy "only admin can delete questions"
  on public.questions for delete
  using ((auth.jwt() ->> 'email') = 'incentivefinanceinfo@gmail.com');
