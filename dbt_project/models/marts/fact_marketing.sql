select
    campaign_id,
    cast(strftime(campaign_date, '%Y%m%d') as integer) as date_key,
    channel, spend, impressions, clicks, conversions, ctr, conversion_rate, cac
from {{ ref('int_marketing_performance') }}
