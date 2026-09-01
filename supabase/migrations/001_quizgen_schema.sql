create extension if not exists pgcrypto;

create table if not exists public.materials (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  filename text not null,
  content_hash text not null,
  mime_type text,
  page_count integer not null default 0,
  chunk_count integer not null default 0,
  created_at timestamptz not null default now(),
  unique (user_id, content_hash)
);

create table if not exists public.exams (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  material_id uuid not null references public.materials(id) on delete cascade,
  mcq_count integer not null check (mcq_count >= 0),
  short_count integer not null check (short_count >= 0),
  duration_minutes integer not null check (duration_minutes between 1 and 180),
  questions jsonb not null default '[]'::jsonb,
  status text not null default 'ready',
  created_at timestamptz not null default now()
);

create table if not exists public.attempts (
  id uuid primary key default gen_random_uuid(),
  exam_id uuid not null references public.exams(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  started_at timestamptz not null default now(),
  expires_at timestamptz not null,
  submitted_at timestamptz,
  status text not null default 'in_progress',
  answers jsonb not null default '{}'::jsonb,
  results jsonb,
  score numeric(5,2),
  auto_submitted boolean not null default false
);

create index if not exists materials_user_id_idx on public.materials(user_id);
create index if not exists exams_user_material_idx on public.exams(user_id, material_id);
create index if not exists attempts_user_id_idx on public.attempts(user_id);

alter table public.materials enable row level security;
alter table public.exams enable row level security;
alter table public.attempts enable row level security;

drop policy if exists "Users read own materials" on public.materials;
create policy "Users read own materials" on public.materials for select to authenticated
using (auth.uid() = user_id);

drop policy if exists "Users read own exams" on public.exams;
create policy "Users read own exams" on public.exams for select to authenticated
using (auth.uid() = user_id);

drop policy if exists "Users read own attempts" on public.attempts;
create policy "Users read own attempts" on public.attempts for select to authenticated
using (auth.uid() = user_id);
