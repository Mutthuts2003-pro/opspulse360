-- Staging: customer master, deduplicated on customer_id
with source as (
    select * from {{ source('raw', 'customers') }}
),
deduped as (
    select *, row_number() over (partition by customer_id order by registration_date desc) as rn
    from source
)
select
    customer_id,
    city,
    state,
    segment,
    cast(registration_date as date) as registration_date
from deduped
where rn = 1 and customer_id is not null
