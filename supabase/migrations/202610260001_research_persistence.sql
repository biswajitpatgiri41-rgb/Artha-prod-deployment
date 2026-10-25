-- Durable research aggregate, event, and report storage.
-- Apply through the project's reviewed Supabase migration process; this file
-- does not execute or claim that a live project has been migrated.
create table if not exists public.research_runs (
    run_id uuid primary key,
    created_at timestamptz not null,
    status text not null,
    payload jsonb not null,
    updated_at timestamptz not null default now()
);

create index if not exists research_runs_created_at_idx
    on public.research_runs (created_at desc);

create table if not exists public.research_events (
    run_id uuid not null references public.research_runs(run_id) on delete cascade,
    event_id text not null,
    event_type text not null,
    occurred_at timestamptz not null,
    payload jsonb not null,
    primary key (run_id, event_id)
);

create index if not exists research_events_run_occurred_idx
    on public.research_events (run_id, occurred_at, event_id);

create table if not exists public.research_reports (
    run_id uuid primary key references public.research_runs(run_id) on delete cascade,
    created_at timestamptz not null,
    report jsonb not null,
    updated_at timestamptz not null default now()
);

-- The application server uses its Supabase server credential via PostgREST.
-- Keep these tables inaccessible to anonymous/authenticated browser roles.
revoke all on public.research_runs, public.research_events, public.research_reports
    from public, anon, authenticated;
grant select, insert, update, delete on public.research_runs,
    public.research_events, public.research_reports to service_role;
