-- Staging: product catalog, deduplicated, invalid prices dropped
with source as (
    select * from {{ source('raw', 'products') }}
),
deduped as (
    select *, row_number() over (partition by product_id order by selling_price desc) as rn
    from source
)
select
    product_id,
    category,
    brand,
    cast(cost as double) as cost,
    cast(selling_price as double) as selling_price,
    supplier_id
from deduped
where rn = 1 and product_id is not null and selling_price > 0
