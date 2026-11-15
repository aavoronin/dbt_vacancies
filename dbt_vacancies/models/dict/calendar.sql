{{ config(
    materialized='table',
    post_hook=[
        "CREATE INDEX IF NOT EXISTS idx_calendar_full_date ON {{ this }} (full_date)",
        "CREATE INDEX IF NOT EXISTS idx_calendar_year ON {{ this }} (year)",
        "CREATE INDEX IF NOT EXISTS idx_calendar_month ON {{ this }} (month)",
        "CREATE INDEX IF NOT EXISTS idx_calendar_is_weekend ON {{ this }} (is_weekend)",
        "CREATE INDEX IF NOT EXISTS idx_calendar_is_holiday ON {{ this }} (is_holiday)"
    ]
) }}

-- =====================================================================
-- 1. Core Date Generation
-- =====================================================================
-- Populates the calendar from 1900-01-01 to 2100-12-31.
-- dbt handles the DROP TABLE and CREATE TABLE automatically.
-- Indexes are applied via the post_hook configuration above.
-- =====================================================================

WITH date_series AS (
    SELECT generate_series('1900-01-01'::DATE, '2100-12-31'::DATE, '1 day'::INTERVAL) AS d
)
SELECT
    -- Surrogate Key (YYYYMMDD)
    TO_CHAR(d, 'YYYYMMDD')::INT AS date_key,
    d::DATE AS full_date,

    -- Year attributes
    EXTRACT(YEAR FROM d)::INT AS year,
    TO_CHAR(d, 'YYYY') AS year_name,
    (EXTRACT(DOY FROM MAKE_DATE(EXTRACT(YEAR FROM d)::INT, 12, 31)) = 366) AS is_leap_year,
    MAKE_DATE(EXTRACT(YEAR FROM d)::INT, 1, 1) AS first_day_of_year,
    MAKE_DATE(EXTRACT(YEAR FROM d)::INT, 12, 31) AS last_day_of_year,
    EXTRACT(DOY FROM MAKE_DATE(EXTRACT(YEAR FROM d)::INT, 12, 31))::INT AS days_in_year,

    -- Quarter attributes
    EXTRACT(QUARTER FROM d)::INT AS quarter,
    'Q' || EXTRACT(QUARTER FROM d)::TEXT AS quarter_name,
    'Q' || EXTRACT(QUARTER FROM d)::TEXT || ' ' || TO_CHAR(d, 'YYYY') AS quarter_year_name,
    MAKE_DATE(EXTRACT(YEAR FROM d)::INT, (EXTRACT(QUARTER FROM d)::INT - 1) * 3 + 1, 1) AS first_day_of_quarter,
    (MAKE_DATE(EXTRACT(YEAR FROM d)::INT, EXTRACT(QUARTER FROM d)::INT * 3, 1) + INTERVAL '1 month - 1 day')::DATE AS last_day_of_quarter,

    -- Month attributes
    EXTRACT(MONTH FROM d)::INT AS month,
    TRIM(TO_CHAR(d, 'Month')) AS month_name,
    TO_CHAR(d, 'Mon') AS month_name_short,
    TRIM(TO_CHAR(d, 'Month')) || ' ' || TO_CHAR(d, 'YYYY') AS month_year_name,
    DATE_TRUNC('month', d)::DATE AS first_day_of_month,
    (DATE_TRUNC('month', d) + INTERVAL '1 month - 1 day')::DATE AS last_day_of_month,
    EXTRACT(DAY FROM (DATE_TRUNC('month', d) + INTERVAL '1 month - 1 day')::DATE)::INT AS days_in_month,

    -- Week attributes
    EXTRACT(WEEK FROM d)::INT AS week_of_year_iso,
    FLOOR((EXTRACT(DAY FROM d)::INT - 1) / 7) + 1 AS week_of_month,
    -- Fixed: Added INTERVAL '1 day' multiplication to prevent type casting errors
    (d - (INTERVAL '1 day' * (EXTRACT(ISODOW FROM d)::INT - 1)))::DATE AS first_day_of_week,
    (d + (INTERVAL '1 day' * (7 - EXTRACT(ISODOW FROM d)::INT)))::DATE AS last_day_of_week,

    -- Day attributes
    EXTRACT(DOY FROM d)::INT AS day_of_year,
    EXTRACT(DAY FROM d)::INT AS day_of_month,
    EXTRACT(ISODOW FROM d)::INT AS day_of_week_iso,
    (EXTRACT(DOW FROM d)::INT + 1) AS day_of_week_us,
    TRIM(TO_CHAR(d, 'Day')) AS day_name,
    TO_CHAR(d, 'Dy') AS day_name_short,

    -- Flags & Business Attributes
    (EXTRACT(ISODOW FROM d) IN (6, 7)) AS is_weekend,
    FALSE AS is_holiday,
    NULL AS holiday_name
FROM date_series