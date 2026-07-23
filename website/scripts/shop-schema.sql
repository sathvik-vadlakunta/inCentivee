-- Run once in Supabase SQL Editor to add persistent shop state per user.

create table if not exists public.user_shop (
  user_id uuid primary key references auth.users(id) on delete cascade,
  purchased text[] not null default '{}',
  active    text[] not null default '{}',
  spent     integer not null default 0,
  updated_at timestamptz not null default now()
);

create or replace function public.set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists user_shop_set_updated_at on public.user_shop;
create trigger user_shop_set_updated_at
  before update on public.user_shop
  for each row execute function public.set_updated_at();

alter table public.user_shop enable row level security;

drop policy if exists "users can read own shop" on public.user_shop;
create policy "users can read own shop"
  on public.user_shop for select
  using (auth.uid() = user_id);

drop policy if exists "users can insert own shop" on public.user_shop;
create policy "users can insert own shop"
  on public.user_shop for insert
  with check (auth.uid() = user_id);

drop policy if exists "users can update own shop" on public.user_shop;
create policy "users can update own shop"
  on public.user_shop for update
  using (auth.uid() = user_id);
