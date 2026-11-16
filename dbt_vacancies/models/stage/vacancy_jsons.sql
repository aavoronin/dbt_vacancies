{{ config(materialized='external_table') }}

CREATE TABLE IF NOT EXISTS {{ this }} (
    vacancy_json_id SERIAL PRIMARY KEY,
    "json" TEXT,
    file_path TEXT NOT NULL UNIQUE,
    file_created_dttm TIMESTAMPTZ,
    file_updated_dttm TIMESTAMPTZ,
    load_id INT
        REFERENCES {{ ref('loads') }} (load_id)
)