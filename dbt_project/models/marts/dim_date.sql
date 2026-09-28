with bounds as (
    select min(order_ts) as min_ts, max(order_ts) as max_ts from {{ ref('stg_orders') }}
),
spine as (
    select unnest(generate_series(
        cast(date_trunc('day', (select min_ts from bounds)) as date),
        cast(date_trunc('day', (select max_ts from bounds)) as date),
        interval 1 day
    )) as full_date
)
select
    cast(strftime(full_date, '%Y%m%d') as integer) as date_key,
    full_date,
    extract(year from full_date) as year,
    extract(quarter from full_date) as quarter,
    extract(month from full_date) as month,
    strftime(full_date, '%B') as month_name,
    extract(day from full_date) as day,
    strftime(full_date, '%A') as day_of_week,
    case when extract(dow from full_date) in (0, 6) then true else false end as is_weekend
from spine
