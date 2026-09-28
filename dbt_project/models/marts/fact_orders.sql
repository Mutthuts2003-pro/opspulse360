select
    order_id as order_key,
    customer_id as customer_key,
    product_id as product_key,
    warehouse_id as warehouse_key,
    cast(strftime(order_ts, '%Y%m%d') as integer) as date_key,
    order_ts,
    quantity,
    amount,
    cost_total,
    margin_amount,
    status
from {{ ref('int_orders_enriched') }}
