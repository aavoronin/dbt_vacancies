{{ config(materialized='external_table') }}

CREATE TABLE IF NOT EXISTS {{ this }} (
    vacancy_to_country_id BIGINT GENERATED ALWAYS AS IDENTITY,
    vacancy_fact_id BIGINT NOT NULL,
    country_id INT NOT NULL,
    load_dttm TIMESTAMPTZ,
    load_id INT,
    source_id INT,
    partition_key INT NOT NULL,
    PRIMARY KEY (partition_key, vacancy_to_country_id),
    FOREIGN KEY (partition_key, vacancy_fact_id)
        REFERENCES {{ ref('vacancy') }} (partition_key, vacancy_fact_id),
    FOREIGN KEY (country_id)
        REFERENCES {{ ref('employer_countries') }} (country_id)
) PARTITION BY RANGE (partition_key)