{{ config(materialized='external_table') }}

CREATE TABLE IF NOT EXISTS {{ this }} (
    employer_city_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    employer_city_name TEXT NOT NULL UNIQUE,
    load_dttm TIMESTAMPTZ,
    load_id INT,
    source_id INT
)