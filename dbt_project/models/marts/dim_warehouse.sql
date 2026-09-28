select distinct warehouse_id as warehouse_key
from {{ ref('stg_inventory') }}
