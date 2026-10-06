-- Preserve the existing table, grants and optional legacy arguments.
create or replace function public.claim_board_sense_free_use(
    p_visitor_hash text,
    p_limit integer,
    p_referral_source text default null,
    p_country_code text default null,
    p_region_code text default null,
    p_city_name text default null
)
returns table (allowed boolean, used_today integer)
language plpgsql
security invoker
set search_path = ''
as $$
declare
    claim_day date := (now() at time zone 'UTC')::date;
    claimed_count integer;
begin
    if p_visitor_hash is null or p_visitor_hash !~ '^[0-9a-f]{32}$'
       or p_limit is null or p_limit < 1 or p_limit > 100 then
        raise exception 'Invalid usage claim' using errcode = '22023';
    end if;

    insert into public.board_sense_public_daily_usage as usage
        (usage_date, visitor_hash, board_count, referral_source,
         country_code, region_code, city_name, first_seen_at, last_seen_at)
    values (claim_day, p_visitor_hash, 1, p_referral_source,
            p_country_code, p_region_code, p_city_name, now(), now())
    on conflict (usage_date, visitor_hash) do update
        set board_count = usage.board_count + 1, last_seen_at = now(),
            referral_source = coalesce(usage.referral_source, excluded.referral_source),
            country_code = coalesce(usage.country_code, excluded.country_code),
            region_code = coalesce(usage.region_code, excluded.region_code),
            city_name = coalesce(usage.city_name, excluded.city_name)
        where usage.board_count < p_limit
    returning board_count into claimed_count;

    if claimed_count is not null then
        return query select true, claimed_count;
    else
        return query select false, usage.board_count
            from public.board_sense_public_daily_usage as usage
            where usage.usage_date = claim_day and usage.visitor_hash = p_visitor_hash;
    end if;
end;
$$;

revoke all on function public.claim_board_sense_free_use(text, integer, text, text, text, text)
    from public, anon, authenticated;
grant execute on function public.claim_board_sense_free_use(text, integer, text, text, text, text)
    to service_role;
