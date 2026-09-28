-- Staging: order transactions, typed and deduplicated
with source as (
    select * from {{ source('raw', 'orders') }}
),
deduped as (
    select *,
        row_number() over (partition by order_id order by "timestamp" desc) as rn
    from source
)
select
    order_id,
    customer_id,
    product_id,
    warehouse_id,
    cast("timestamp" as timestamp) as order_ts,
    cast(quantity as integer) as quantity,
    cast(amount as double) as amount,
    status
from deduped
where rn = 1
  and order_id is not null
  and amount >= 0
