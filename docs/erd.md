# OpsPulse 360 — Data Model / ERD

Star schema implemented in the Gold layer (`warehouse/gold/build_gold.py`)
and mirrored by the dbt marts (`dbt_project/models/marts/`).

```mermaid
erDiagram
    DIM_CUSTOMER ||--o{ FACT_ORDERS : "customer_key"
    DIM_PRODUCT  ||--o{ FACT_ORDERS : "product_key"
    DIM_WAREHOUSE ||--o{ FACT_ORDERS : "warehouse_key"
    DIM_DATE     ||--o{ FACT_ORDERS : "date_key"

    DIM_PRODUCT  ||--o{ FACT_INVENTORY : "product_key"
    DIM_WAREHOUSE ||--o{ FACT_INVENTORY : "warehouse_key"

    FACT_ORDERS  ||--o| FACT_DELIVERY : "order_key"
    DIM_WAREHOUSE ||--o{ FACT_DELIVERY : "warehouse_key"

    DIM_DATE     ||--o{ FACT_MARKETING : "date_key"

    DIM_CUSTOMER {
        string customer_key PK
        string city
        string state
        string segment
        date   registration_date
    }

    DIM_PRODUCT {
        string product_key PK
        string category
        string brand
        float  cost
        float  selling_price
        float  margin_pct
        string supplier_id
    }

    DIM_WAREHOUSE {
        string warehouse_key PK
    }

    DIM_DATE {
        int    date_key PK
        date   full_date
        int    year
        int    quarter
        int    month
        string month_name
        int    day
        string day_of_week
        bool   is_weekend
    }

    FACT_ORDERS {
        string order_key PK
        string customer_key FK
        string product_key FK
        string warehouse_key FK
        int    date_key FK
        datetime timestamp
        int    quantity
        float  amount
        float  cost_total
        float  margin_amount
        string status
    }

    FACT_INVENTORY {
        string warehouse_key FK
        string product_key FK
        int    date_key FK
        int    available_qty
        int    reserved_qty
        int    reorder_level
        int    stock_position
        bool   below_reorder_level
        datetime updated_at
    }

    FACT_DELIVERY {
        string order_key PK_FK
        string warehouse_key FK
        string partner
        int    date_key FK
        datetime pickup_time
        datetime expected_delivery
        datetime actual_delivery
        float  delivery_hours
        bool   sla_breached
        string status
    }

    FACT_MARKETING {
        string campaign_id PK
        int    date_key FK
        string channel
        float  spend
        int    impressions
        int    clicks
        int    conversions
        float  ctr
        float  conversion_rate
        float  cac
    }
```

## Grain of each fact table

| Fact table | Grain (one row per...) |
|---|---|
| `fact_orders` | one order line (one product on one order) |
| `fact_inventory` | one warehouse/product inventory snapshot |
| `fact_delivery` | one order's delivery record |
| `fact_marketing` | one campaign, one day |

## Why a star schema (interview question §15)

A star schema was chosen over a normalized (3NF) or snowflake design because:
- **Query simplicity** — BI/dashboard queries (revenue by category by month,
  SLA breach % by partner) need only single-hop joins from fact to dimension.
- **Read-optimized** — this is an analytical workload (far more reads than
  writes), so the denormalized dimensions trade some storage/update
  complexity for much faster aggregate queries.
- **Conformed dimensions** — `dim_customer`, `dim_product`, `dim_warehouse`,
  and `dim_date` are shared across all four fact tables, so metrics from
  different business processes (orders, inventory, delivery, marketing) can
  be compared/joined on the same dimension keys.
- **BI-tool friendly** — most BI tools (and dbt's own testing conventions)
  assume/optimize for a star schema.
