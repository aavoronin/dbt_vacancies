{{ config(materialized='external_table') }}

CREATE TABLE IF NOT EXISTS {{ this }} (
    employment_type_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    employment_type_name TEXT NOT NULL UNIQUE,
    load_dttm TIMESTAMPTZ,
    load_id INT,
    source_id INT
)