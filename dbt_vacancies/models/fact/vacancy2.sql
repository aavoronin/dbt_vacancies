{{ config(materialized='external_table') }}

CREATE TABLE IF NOT EXISTS {{ this }} (
    vacancy_fact_id BIGINT NOT NULL,
    partition_key INT NOT NULL,
    vacancy_url TEXT,
    apply_url TEXT,
    json_path TEXT,
    txt_path TEXT,
    html_path TEXT,
    search_url TEXT,
    job_id TEXT,
    applicants_count_raw TEXT,
    PRIMARY KEY (partition_key, vacancy_fact_id),
    FOREIGN KEY (partition_key, vacancy_fact_id)
        REFERENCES {{ ref('vacancy') }} (partition_key, vacancy_fact_id)
) PARTITION BY RANGE (partition_key)