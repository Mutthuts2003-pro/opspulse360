-- Intermediate: marketing performance ratios (CTR, conversion rate, CAC)
select
    campaign_id,
    campaign_date,
    channel,
    spend,
    impressions,
    clicks,
    conversions,
    case when impressions > 0 then round(clicks::double / impressions, 4) else 0 end as ctr,
    case when clicks > 0 then round(conversions::double / clicks, 4) else 0 end as conversion_rate,
    case when conversions > 0 then round(spend / conversions, 2) else null end as cac
from {{ ref('stg_marketing') }}
