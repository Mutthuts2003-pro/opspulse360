-- Staging: customer support tickets
with source as (
    select * from {{ source('raw', 'support') }}
),
deduped as (
    select *, row_number() over (partition by ticket_id order by created_at desc) as rn
    from source
)
select
    ticket_id,
    customer_id,
    order_id,
    issue_type,
    priority,
    cast(created_at as timestamp) as created_at,
    try_cast(resolved_at as timestamp) as resolved_at
from deduped
where rn = 1 and ticket_id is not null
