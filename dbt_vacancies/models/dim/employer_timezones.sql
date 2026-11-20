{{ config(materialized='external_table') }}

CREATE TABLE IF NOT EXISTS {{ this }} (
    employer_timezone_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    employer_timezone_name TEXT NOT NULL UNIQUE,
    load_dttm TIMESTAMPTZ,
    load_id INT,
    source_id INT
)