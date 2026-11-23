{{ config(materialized='table') }}

WITH grouped_vacancies AS (
    SELECT
        v.saved_date_id AS date_key,
        vtl.language_id,
        vtec.country_id,
        COUNT(DISTINCT v.vacancy_fact_id) AS vacancy_count
    FROM {{ ref('vacancy') }} v
    JOIN {{ ref('vacancy_to_required_languages') }} vtl
        ON v.vacancy_fact_id = vtl.vacancy_fact_id
        AND v.partition_key = vtl.partition_key
    LEFT JOIN {{ ref('vacancy_to_employer_countries') }} vtec
        ON v.vacancy_fact_id = vtec.vacancy_fact_id
        AND v.partition_key = vtec.partition_key
    GROUP BY
        v.saved_date_id,
        vtl.language_id,
        vtec.country_id
)
SELECT
    gv.date_key,
    c.full_date AS date,
    gv.language_id,
    l.language_name AS required_language,
    gv.country_id,
    ec.country_name AS country_of_employer,
    gv.vacancy_count
FROM grouped_vacancies gv
JOIN {{ ref('calendar') }} c
    ON gv.date_key = c.date_key
JOIN {{ ref('required_languages') }} l
    ON gv.language_id = l.language_id
LEFT JOIN {{ ref('employer_countries') }} ec
    ON gv.country_id = ec.country_id