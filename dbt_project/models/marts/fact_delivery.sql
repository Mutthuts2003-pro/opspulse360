select
    order_id as order_key,
    warehouse_id as warehouse_key,
    partner,
    cast(strftime(pickup_time, '%Y%m%d') as integer) as date_key,
    pickup_time, expected_delivery, actual_delivery,
    delivery_hours, sla_breached, status
from {{ ref('int_delivery_performance') }}
