{{ config(materialized='external_table') }}

CREATE TABLE IF NOT EXISTS {{ this }} (
    period_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    period_name TEXT NOT NULL UNIQUE,
    load_dttm TIMESTAMPTZ,
    load_id INT,
    source_id INT
)