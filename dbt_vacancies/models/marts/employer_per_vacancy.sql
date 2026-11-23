{{ config(materialized='table') }}

WITH grouped_vacancies AS (
    SELECT
        v.saved_date_id AS date_key,
        v.company_id AS employer_id,
        vtec.country_id,
        COUNT(DISTINCT v.vacancy_fact_id) AS vacancy_count
    FROM {{ ref('vacancy') }} v
    LEFT JOIN {{ ref('vacancy_to_employer_countries') }} vtec
        ON v.vacancy_fact_id = vtec.vacancy_fact_id
        AND v.partition_key = vtec.partition_key
    GROUP BY
        v.saved_date_id,
        v.company_id,
        vtec.country_id
)
SELECT
    gv.date_key,
    c.full_date AS date,
    gv.employer_id,
    comp.company_name AS employer,
    gv.country_id,
    ec.country_name AS country_of_employer,
    gv.vacancy_count
FROM grouped_vacancies gv
JOIN {{ ref('calendar') }} c
    ON gv.date_key = c.date_key
JOIN {{ ref('companies') }} comp
    ON gv.employer_id = comp.company_id
LEFT JOIN {{ ref('employer_countries') }} ec
    ON gv.country_id = ec.country_id