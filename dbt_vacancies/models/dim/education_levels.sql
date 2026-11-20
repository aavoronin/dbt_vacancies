{{ config(materialized='external_table') }}

CREATE TABLE IF NOT EXISTS {{ this }} (
    education_level_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    education_level_name TEXT NOT NULL UNIQUE,
    load_dttm TIMESTAMPTZ,
    load_id INT,
    source_id INT
)