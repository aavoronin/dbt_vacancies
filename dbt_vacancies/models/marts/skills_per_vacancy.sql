{{ config(materialized='table') }}

WITH grouped_vacancies AS (
    SELECT
        v.saved_date_id AS date_key,
        vts.skill_id,
        COUNT(DISTINCT v.vacancy_fact_id) AS vacancy_count
    FROM {{ ref('vacancy') }} v
    JOIN {{ ref('vacancy_to_skills') }} vts
        ON v.vacancy_fact_id = vts.vacancy_fact_id
        AND v.partition_key = vts.partition_key
    GROUP BY
        v.saved_date_id,
        vts.skill_id
)
SELECT
    gv.date_key,
    c.full_date AS date,
    gv.skill_id,
    s.skill_name AS skill,
    gv.vacancy_count
FROM grouped_vacancies gv
JOIN {{ ref('calendar') }} c
    ON gv.date_key = c.date_key
JOIN {{ ref('skills') }} s
    ON gv.skill_id = s.skill_id