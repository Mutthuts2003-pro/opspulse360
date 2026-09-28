select
    customer_id as customer_key,
    city, state, segment, registration_date
from {{ ref('stg_customers') }}
