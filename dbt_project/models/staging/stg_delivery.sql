-- Staging: delivery / shipment records
with source as (
    select * from {{ source('raw', 'delivery') }}
),
deduped as (
    select *, row_number() over (partition by order_id order by actual_delivery desc) as rn
    from source
)
select
    order_id,
    partner,
    cast(pickup_time as timestamp) as pickup_time,
    cast(expected_delivery as timestamp) as expected_delivery,
    cast(actual_delivery as timestamp) as actual_delivery,
    status
from deduped
where rn = 1 and order_id is not null
