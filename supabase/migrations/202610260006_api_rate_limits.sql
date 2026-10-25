-- Shared, atomic per-route request throttling for expensive API operations.
create table if not exists public.api_rate_limits (
    key_hash text primary key,
    window_start bigint not null,
    request_count integer not null check (request_count >= 1)
);

alter table public.api_rate_limits enable row level security;
revoke all on public.api_rate_limits from public, anon, authenticated;
grant select, insert, update, delete on public.api_rate_limits to service_role;

create or replace function public.consume_api_rate_limit(
    p_key_hash text,
    p_limit integer,
    p_window_seconds integer
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
       or p_limit < 1 or p_limit > 10000
       or p_window_seconds < 1 or p_window_seconds > 86400 then
        raise exception 'Invalid API rate limit arguments';
    end if;
    v_window := (extract(epoch from clock_timestamp())::bigint / p_window_seconds) * p_window_seconds;
    insert into public.api_rate_limits(key_hash, window_start, request_count)
    values (p_key_hash, v_window, 1)
    on conflict (key_hash) do update set
        request_count = case
            when public.api_rate_limits.window_start = excluded.window_start
                then public.api_rate_limits.request_count + 1
            else 1
        end,
        window_start = excluded.window_start
    returning request_count into v_count;
    delete from public.api_rate_limits
    where window_start < v_window - 86400;
    return v_count <= p_limit;
end;
$$;

revoke all on function public.consume_api_rate_limit(text, integer, integer)
    from public, anon, authenticated;
grant execute on function public.consume_api_rate_limit(text, integer, integer)
    to service_role;
