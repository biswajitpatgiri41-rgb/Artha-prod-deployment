-- Shared, atomic login throttling across API workers and serverless instances.
create table if not exists public.auth_login_rate_limits (
    key_hash text primary key,
    window_start bigint not null,
    attempt_count integer not null check (attempt_count >= 1)
);

alter table public.auth_login_rate_limits enable row level security;
revoke all on public.auth_login_rate_limits from public, anon, authenticated;
grant select, insert, update, delete on public.auth_login_rate_limits to service_role;

create or replace function public.consume_admin_login_attempt(
    p_key_hash text,
    p_limit integer default 5,
    p_window_seconds integer default 60
)
returns boolean
language plpgsql
security invoker
set search_path = ''
as $$
declare
    v_window bigint;
    v_count integer;
begin
    if p_key_hash is null or length(p_key_hash) <> 64
       or p_limit < 1 or p_limit > 20
       or p_window_seconds < 10 or p_window_seconds > 3600 then
        raise exception 'Invalid login limiter arguments';
    end if;
    v_window := (extract(epoch from clock_timestamp())::bigint / p_window_seconds) * p_window_seconds;
    insert into public.auth_login_rate_limits(key_hash, window_start, attempt_count)
    values (p_key_hash, v_window, 1)
    on conflict (key_hash) do update set
        attempt_count = case
            when public.auth_login_rate_limits.window_start = excluded.window_start
                then public.auth_login_rate_limits.attempt_count + 1
            else 1
        end,
        window_start = excluded.window_start
    returning attempt_count into v_count;
    delete from public.auth_login_rate_limits
    where window_start < v_window - 86400;
    return v_count <= p_limit;
end;
$$;

revoke all on function public.consume_admin_login_attempt(text, integer, integer)
    from public, anon, authenticated;
grant execute on function public.consume_admin_login_attempt(text, integer, integer)
    to service_role;
