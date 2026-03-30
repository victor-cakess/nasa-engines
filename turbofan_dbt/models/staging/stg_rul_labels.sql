{{ config(materialized='view') }}

select
    unit,
    rul
from {{ source('raw', 'rul_fd001') }}
