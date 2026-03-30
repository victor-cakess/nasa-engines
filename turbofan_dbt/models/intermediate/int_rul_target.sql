{{ config(materialized='view') }}

with max_cycles as (
    select
        unit,
        max(cycle) as max_cycle
    from {{ ref('stg_sensor_readings') }}
    group by unit
),

rul as (
    select
        s.unit,
        s.cycle,
        m.max_cycle - s.cycle as rul
    from {{ ref('stg_sensor_readings') }} s
    join max_cycles m on s.unit = m.unit
)

select
    unit,
    cycle,
    rul,
    least(rul, 125) as rul_capped
from rul
