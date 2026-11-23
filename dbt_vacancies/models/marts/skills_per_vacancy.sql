{{ config(materialized='table') }}

WITH grouped_vacancies AS (
    SELECT
        v.saved_date_id AS date_key,
        vts.skill_id,
        vtec.country_id,
        COUNT(DISTINCT v.vacancy_fact_id) AS vacancy_count
    FROM {{ ref('vacancy') }} v
    JOIN {{ ref('vacancy_to_skills') }} vts
        ON v.vacancy_fact_id = vts.vacancy_fact_id
        AND v.partition_key = vts.partition_key
    LEFT JOIN {{ ref('vacancy_to_employer_countries') }} vtec
        ON v.vacancy_fact_id = vtec.vacancy_fact_id
        AND v.partition_key = vtec.partition_key
    GROUP BY
        v.saved_date_id,
        vts.skill_id,
        vtec.country_id
)
SELECT
    gv.date_key,
    c.full_date AS date,
    gv.skill_id,
    s.skill_name AS skill,
    gv.country_id,
    ec.country_name AS country_of_employer,
    gv.vacancy_count
FROM grouped_vacancies gv
JOIN {{ ref('calendar') }} c
    ON gv.date_key = c.date_key
JOIN {{ ref('skills') }} s
    ON gv.skill_id = s.skill_id
LEFT JOIN {{ ref('employer_countries') }} ec
    ON gv.country_id = ec.country_id