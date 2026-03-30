{{ config(materialized='table') }}

with window_def as (
    select
        unit,
        cycle,

        -- raw sensors
        s2, s3, s4, s7, s8, s9, s11, s12, s13, s14, s15, s17, s20, s21,

        -- rolling means
        avg(s2)  over w as s2_mean,
        avg(s3)  over w as s3_mean,
        avg(s4)  over w as s4_mean,
        avg(s7)  over w as s7_mean,
        avg(s8)  over w as s8_mean,
        avg(s9)  over w as s9_mean,
        avg(s11) over w as s11_mean,
        avg(s12) over w as s12_mean,
        avg(s13) over w as s13_mean,
        avg(s14) over w as s14_mean,
        avg(s15) over w as s15_mean,
        avg(s17) over w as s17_mean,
        avg(s20) over w as s20_mean,
        avg(s21) over w as s21_mean,

        -- rolling standard deviations (null on first row → 0)
        coalesce(stddev(s2)  over w, 0) as s2_std,
        coalesce(stddev(s3)  over w, 0) as s3_std,
        coalesce(stddev(s4)  over w, 0) as s4_std,
        coalesce(stddev(s7)  over w, 0) as s7_std,
        coalesce(stddev(s8)  over w, 0) as s8_std,
        coalesce(stddev(s9)  over w, 0) as s9_std,
        coalesce(stddev(s11) over w, 0) as s11_std,
        coalesce(stddev(s12) over w, 0) as s12_std,
        coalesce(stddev(s13) over w, 0) as s13_std,
        coalesce(stddev(s14) over w, 0) as s14_std,
        coalesce(stddev(s15) over w, 0) as s15_std,
        coalesce(stddev(s17) over w, 0) as s17_std,
        coalesce(stddev(s20) over w, 0) as s20_std,
        coalesce(stddev(s21) over w, 0) as s21_std

    from {{ ref('stg_sensor_readings') }}
    window w as (
        partition by unit
        order by cycle
        rows between 29 preceding and current row
    )
)

select * from window_def
