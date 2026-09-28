-- Staging: latest inventory snapshot per warehouse/product
with source as (
    select * from {{ source('raw', 'inventory') }}
),
deduped as (
    select *, row_number() over (
        partition by warehouse_id, product_id order by updated_at desc
    ) as rn
    from source
)
select
    warehouse_id,
    product_id,
    cast(available_qty as integer) as available_qty,
    cast(reserved_qty as integer) as reserved_qty,
    cast(reorder_level as integer) as reorder_level,
    cast(updated_at as timestamp) as updated_at
from deduped
where rn = 1 and available_qty >= 0 and reserved_qty >= 0
