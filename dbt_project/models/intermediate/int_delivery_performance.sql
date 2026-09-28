-- Intermediate: delivery records with SLA breach flag and delivery duration
select
    d.order_id,
    d.partner,
    d.pickup_time,
    d.expected_delivery,
    d.actual_delivery,
    d.status,
    o.warehouse_id,
    date_diff('hour', d.pickup_time, d.actual_delivery) as delivery_hours,
    case when d.actual_delivery > d.expected_delivery then true else false end as sla_breached
from {{ ref('stg_delivery') }} d
left join {{ ref('stg_orders') }} o on d.order_id = o.order_id
