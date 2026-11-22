{{ config(materialized='table') }}

SELECT
    c.full_date AS date,
    cert.certification_name AS cert,
    cert.exam_code AS cert_code,
    ec.country_name AS country_of_employer,
    COUNT(DISTINCT v.vacancy_fact_id) AS vacancy_count
FROM {{ ref('vacancy') }} v
JOIN {{ ref('vacancy_to_certifications') }} vtc
    ON v.vacancy_fact_id = vtc.vacancy_fact_id
    AND v.partition_key = vtc.partition_key
JOIN {{ ref('certifications') }} cert
    ON vtc.certification_id = cert.certification_id
JOIN {{ ref('vacancy_to_employer_countries') }} vtec
    ON v.vacancy_fact_id = vtec.vacancy_fact_id
    AND v.partition_key = vtec.partition_key
JOIN {{ ref('employer_countries') }} ec
    ON vtec.country_id = ec.country_id
JOIN {{ ref('calendar') }} c
    ON v.saved_date_id = c.date_key
GROUP BY
    c.full_date,
    cert.certification_name,
    cert.exam_code,
    ec.country_name