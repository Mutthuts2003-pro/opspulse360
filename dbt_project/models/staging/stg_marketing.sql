-- Staging: daily marketing campaign performance
with source as (
    select * from {{ source('raw', 'marketing') }}
),
deduped as (
    select *, row_number() over (
        partition by campaign_id, "date", channel order by spend desc
    ) as rn
    from source
)
select
    campaign_id,
    cast("date" as date) as campaign_date,
    channel,
    cast(spend as double) as spend,
    cast(impressions as integer) as impressions,
    cast(clicks as integer) as clicks,
    cast(conversions as integer) as conversions
from deduped
where rn = 1
