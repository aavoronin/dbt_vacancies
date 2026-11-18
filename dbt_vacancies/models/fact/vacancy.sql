{{ config(
    materialized='external_table',
    post_hook=[
        "ALTER TABLE {{ this }} ADD COLUMN IF NOT EXISTS modified_timestamp TIMESTAMPTZ",
        "ALTER TABLE {{ this }} ADD COLUMN IF NOT EXISTS version INT"
    ]
) }}

CREATE TABLE IF NOT EXISTS {{ this }} (
    vacancy_fact_id BIGINT GENERATED ALWAYS AS IDENTITY,
    vacancy_json_id INT,
    saved_date_id INT,
    parsed_date_id INT,
    file_created_date_id INT,
    file_updated_date_id INT,
    model_id INT,
    title_id INT,
    level_id INT,
    employment_type_id INT,
    contract_type_id INT,
    company_id INT,
    company_industry_id INT,
    vacancy_site_id INT,
    vacancy_id INT,
    score NUMERIC,
    score_percentile NUMERIC,
    load_dttm TIMESTAMPTZ,
    load_id INT,
    source_id INT,
    partition_key INT,
    modified_timestamp TIMESTAMPTZ,
    version INT,
    PRIMARY KEY (partition_key, vacancy_fact_id)
) PARTITION BY RANGE (partition_key)