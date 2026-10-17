-- Verdict: API keys and per-day usage. Apply once in the Supabase SQL editor.
-- The API server uses the service role key (bypasses RLS); signed-in users may only read their own rows.

create table if not exists public.api_keys (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references auth.users (id) on delete cascade,
  name          text not null check (char_length(name) between 1 and 64),
  prefix        text not null,                 -- first characters of the key, safe to display
  key_hash      text not null unique,          -- sha256 hex of the full key; the key itself is never stored
  created_at    timestamptz not null default now(),
  revoked_at    timestamptz,
  monthly_quota integer not null default 10000 check (monthly_quota >= 0)
);

create index if not exists api_keys_user_idx on public.api_keys (user_id, created_at desc);

create table if not exists public.usage_daily (
  key_id uuid not null references public.api_keys (id) on delete cascade,
  day    date not null,
  count  integer not null default 0,
  primary key (key_id, day)
);

alter table public.api_keys    enable row level security;
alter table public.usage_daily enable row level security;

drop policy if exists "users read own keys" on public.api_keys;
create policy "users read own keys" on public.api_keys
  for select to authenticated using (user_id = auth.uid());

drop policy if exists "users read own usage" on public.usage_daily;
create policy "users read own usage" on public.usage_daily
  for select to authenticated
  using (exists (select 1 from public.api_keys k where k.id = usage_daily.key_id and k.user_id = auth.uid()));

-- No insert/update/delete policies: writes go through the API with the service role.
-- Hide the hash from the client roles even for the owner.
revoke all on public.api_keys, public.usage_daily from anon, authenticated;
grant select (id, user_id, name, prefix, created_at, revoked_at, monthly_quota) on public.api_keys to authenticated;
grant select on public.usage_daily to authenticated;
