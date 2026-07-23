-- Run in Supabase SQL Editor to add peak_coins tracking to user_shop.
alter table public.user_shop
  add column if not exists peak_coins integer not null default 0;
