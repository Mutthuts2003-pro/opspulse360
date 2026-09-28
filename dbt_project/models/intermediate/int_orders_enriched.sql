-- Intermediate: orders enriched with product cost/margin and customer segment
select
    o.order_id,
    o.customer_id,
    o.product_id,
    o.warehouse_id,
    o.order_ts,
    o.quantity,
    o.amount,
    o.status,
    p.category,
    p.brand,
    p.cost as unit_cost,
    (p.cost * o.quantity) as cost_total,
    (o.amount - (p.cost * o.quantity)) as margin_amount,
    c.segment as customer_segment,
    c.city as customer_city
from {{ ref('stg_orders') }} o
left join {{ ref('stg_products') }} p on o.product_id = p.product_id
left join {{ ref('stg_customers') }} c on o.customer_id = c.customer_id
