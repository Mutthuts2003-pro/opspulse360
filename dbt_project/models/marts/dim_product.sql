select
    product_id as product_key,
    category, brand, cost, selling_price,
    round((selling_price - cost) / nullif(selling_price, 0), 4) as margin_pct,
    supplier_id
from {{ ref('stg_products') }}
