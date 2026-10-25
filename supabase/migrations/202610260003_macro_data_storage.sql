-- Durable canonical macro series and provenance for production data uploads.
create table if not exists public.macro_observations (
    series_id text not null,
    obs_date date not null,
    value double precision not null,
    unit text not null,
    frequency text not null,
    source text not null,
    source_url text,
    release_date date,
    base_year text,
    seasonal_adjustment text,
    revision_tag text,
    retrieved_at timestamptz not null default now(),
    primary key (series_id, obs_date),
    constraint macro_observations_value_finite check (value > '-Infinity'::float8 and value < 'Infinity'::float8)
);

create index if not exists macro_observations_series_date_idx
    on public.macro_observations (series_id, obs_date);

create table if not exists public.data_uploads (
    upload_id text primary key,
    series_id text not null,
    uploaded_at timestamptz not null default now(),
    object_key text not null,
    manifest jsonb not null
);

alter table public.macro_observations enable row level security;
alter table public.data_uploads enable row level security;
revoke all on public.macro_observations, public.data_uploads from public, anon, authenticated;
grant select, insert, update, delete on public.macro_observations, public.data_uploads to service_role;

create or replace function public.save_macro_observations(
    p_series_id text,
    p_observations jsonb,
    p_replace boolean default false,
    p_upload_id text default null,
    p_object_key text default null,
    p_manifest jsonb default null
)
returns integer
language plpgsql
security invoker
set search_path = ''
as $$
declare
    v_count integer := 0;
begin
    if p_series_id is null or length(p_series_id) = 0
       or jsonb_typeof(p_observations) <> 'array'
       or jsonb_array_length(p_observations) > 500000 then
        raise exception 'Invalid macro observations payload';
    end if;
    if (p_upload_id is null) <> (p_object_key is null)
       or (p_upload_id is null) <> (p_manifest is null) then
        raise exception 'Upload provenance fields must be provided together';
    end if;

    if p_replace then
        delete from public.macro_observations where series_id = p_series_id;
    end if;

    insert into public.macro_observations(
        series_id, obs_date, value, unit, frequency, source, source_url,
        release_date, base_year, seasonal_adjustment, revision_tag, retrieved_at
    )
    select p_series_id, item.obs_date, item.value, item.unit, item.frequency,
           item.source, item.source_url, item.release_date, item.base_year,
           item.seasonal_adjustment, item.revision_tag,
           coalesce(item.retrieved_at, now())
    from jsonb_to_recordset(p_observations) as item(
        obs_date date, value double precision, unit text, frequency text,
        source text, source_url text, release_date date, base_year text,
        seasonal_adjustment text, revision_tag text, retrieved_at timestamptz
    )
    on conflict (series_id, obs_date) do update set
        value = excluded.value, unit = excluded.unit, frequency = excluded.frequency,
        source = excluded.source, source_url = excluded.source_url,
        release_date = excluded.release_date, base_year = excluded.base_year,
        seasonal_adjustment = excluded.seasonal_adjustment,
        revision_tag = excluded.revision_tag, retrieved_at = excluded.retrieved_at;
    get diagnostics v_count = row_count;

    if p_upload_id is not null then
        insert into public.data_uploads(upload_id, series_id, uploaded_at, object_key, manifest)
        values (p_upload_id, p_series_id, now(), p_object_key, p_manifest)
        on conflict (upload_id) do nothing;
    end if;
    return v_count;
end;
$$;

revoke all on function public.save_macro_observations(text, jsonb, boolean, text, text, jsonb)
    from public, anon, authenticated;
grant execute on function public.save_macro_observations(text, jsonb, boolean, text, text, jsonb)
    to service_role;

insert into storage.buckets (id, name, public)
values ('macro-uploads', 'macro-uploads', false)
on conflict (id) do update set public = false;
