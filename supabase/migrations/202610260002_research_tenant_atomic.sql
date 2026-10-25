-- Tenant isolation and a single-transaction write boundary for research records.
alter table public.research_runs
    add column if not exists tenant_id text not null default 'system';

create index if not exists research_runs_tenant_created_idx
    on public.research_runs (tenant_id, created_at desc);

create or replace function public.persist_research_record(p_run jsonb)
returns void
language plpgsql
security invoker
set search_path = ''
as $$
declare
    v_run_id uuid := (p_run->>'run_id')::uuid;
    v_tenant_id text := coalesce(nullif(p_run->>'tenant_id', ''), 'system');
    v_created_at timestamptz := (p_run->>'created_at')::timestamptz;
    v_updated_at timestamptz := now();
    v_event jsonb;
    v_index integer := 0;
    v_written uuid;
    v_report jsonb := p_run->'report';
begin
    if v_run_id is null or v_created_at is null or jsonb_typeof(p_run) <> 'object' then
        raise exception 'Invalid research record';
    end if;

    insert into public.research_runs(run_id, tenant_id, created_at, status, payload, updated_at)
    values (v_run_id, v_tenant_id, v_created_at,
            coalesce(p_run->>'status', 'completed'), p_run, v_updated_at)
    on conflict (run_id) do update set
        status = excluded.status,
        payload = excluded.payload,
        updated_at = excluded.updated_at
    where public.research_runs.tenant_id = excluded.tenant_id
    returning run_id into v_written;

    if v_written is null then
        raise exception 'Research run tenant ownership conflict';
    end if;

    for v_event in select value from jsonb_array_elements(coalesce(p_run->'events', '[]'::jsonb))
    loop
        insert into public.research_events(run_id, event_id, event_type, occurred_at, payload)
        values (
            v_run_id,
            coalesce(nullif(v_event->>'event_id', ''), v_run_id::text || ':' || v_index::text),
            coalesce(nullif(v_event->>'event_type', ''), nullif(v_event->>'type', ''), 'unknown'),
            coalesce(nullif(v_event->>'occurred_at', '')::timestamptz,
                     nullif(v_event->>'created_at', '')::timestamptz, v_updated_at),
            v_event
        )
        on conflict (run_id, event_id) do update set
            event_type = excluded.event_type,
            occurred_at = excluded.occurred_at,
            payload = excluded.payload;
        v_index := v_index + 1;
    end loop;

    if jsonb_typeof(v_report) = 'object' then
        insert into public.research_reports(run_id, created_at, report, updated_at)
        values (v_run_id,
                coalesce(nullif(v_report->>'created_at', '')::timestamptz, v_created_at),
                v_report, v_updated_at)
        on conflict (run_id) do update set
            report = excluded.report,
            updated_at = excluded.updated_at;
    end if;
end;
$$;

revoke all on function public.persist_research_record(jsonb) from public, anon, authenticated;
grant execute on function public.persist_research_record(jsonb) to service_role;
revoke all on public.research_runs, public.research_events, public.research_reports
    from public, anon, authenticated;
grant select, insert, update, delete on public.research_runs,
    public.research_events, public.research_reports to service_role;
