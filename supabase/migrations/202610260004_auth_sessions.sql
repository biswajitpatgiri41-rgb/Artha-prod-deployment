-- Shared, revocable sessions for multi-worker production API deployments.
create table if not exists public.auth_sessions (
    session_hash text primary key,
    user_id text not null,
    email text not null,
    role text not null,
    tenant_id text not null,
    permissions jsonb not null default '[]'::jsonb,
    mfa_verified boolean not null default false,
    created_at double precision not null,
    last_activity double precision not null,
    ip_address text,
    user_agent text,
    revoked boolean not null default false
);

create index if not exists auth_sessions_user_id_idx
    on public.auth_sessions (user_id);

alter table public.auth_sessions enable row level security;
revoke all on public.auth_sessions from public, anon, authenticated;
grant select, insert, update, delete on public.auth_sessions to service_role;
