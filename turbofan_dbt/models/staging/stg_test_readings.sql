{{ config(materialized='view') }}

select
    unit,
    cycle,
    s2,
    s3,
    s4,
    s7,
    s8,
    s9,
    s11,
    s12,
    s13,
    s14,
    s15,
    s17,
    s20,
    s21
from {{ source('raw', 'test_fd001') }}
