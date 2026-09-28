-- Intermediate: inventory position vs. reorder level
select
    warehouse_id,
    product_id,
    available_qty,
    reserved_qty,
    (available_qty - reserved_qty) as stock_position,
    reorder_level,
    case when (available_qty - reserved_qty) < reorder_level then true else false end as below_reorder_level,
    updated_at
from {{ ref('stg_inventory') }}
