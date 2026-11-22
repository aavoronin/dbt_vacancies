{{ config(materialized='table') }}

SELECT
    c.full_date AS date,
    l.language_name AS required_language,
    ec.country_name AS country_of_employer,
    COUNT(DISTINCT v.vacancy_fact_id) AS vacancy_count
FROM {{ ref('vacancy') }} v
JOIN {{ ref('vacancy_to_required_languages') }} vtl
    ON v.vacancy_fact_id = vtl.vacancy_fact_id
    AND v.partition_key = vtl.partition_key
JOIN {{ ref('required_languages') }} l
    ON vtl.language_id = l.language_id
JOIN {{ ref('vacancy_to_employer_countries') }} vtec
    ON v.vacancy_fact_id = vtec.vacancy_fact_id
    AND v.partition_key = vtec.partition_key
JOIN {{ ref('employer_countries') }} ec
    ON vtec.country_id = ec.country_id
JOIN {{ ref('calendar') }} c
    ON v.saved_date_id = c.date_key
GROUP BY
    c.full_date,
    l.language_name,
    ec.country_name