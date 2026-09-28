select
    warehouse_id as warehouse_key,
    product_id as product_key,
    cast(strftime(updated_at, '%Y%m%d') as integer) as date_key,
    available_qty, reserved_qty, stock_position,
    reorder_level, below_reorder_level, updated_at
from {{ ref('int_inventory_position') }}
