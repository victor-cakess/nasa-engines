{{ config(materialized='table') }}

select
    r.*,
    t.rul,
    t.rul_capped
from {{ ref('int_rolling_features') }} r
join {{ ref('int_rul_target') }} t
    on r.unit = t.unit
    and r.cycle = t.cycle
