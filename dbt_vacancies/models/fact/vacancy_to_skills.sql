{{ config(materialized='external_table') }}

CREATE TABLE IF NOT EXISTS {{ this }} (
    vacancy_to_skill_id BIGINT GENERATED ALWAYS AS IDENTITY,
    vacancy_fact_id BIGINT NOT NULL,
    skill_level_id INT NOT NULL,
    skill_id INT NOT NULL,
    load_dttm TIMESTAMPTZ,
    load_id INT,
    source_id INT,
    partition_key INT NOT NULL,
    PRIMARY KEY (partition_key, vacancy_to_skill_id),
    FOREIGN KEY (partition_key, vacancy_fact_id)
        REFERENCES {{ ref('vacancy') }} (partition_key, vacancy_fact_id),
    FOREIGN KEY (skill_level_id)
        REFERENCES {{ ref('skill_levels') }} (skill_level_id),
    FOREIGN KEY (skill_id)
        REFERENCES {{ ref('skills') }} (skill_id)
) PARTITION BY RANGE (partition_key)