{{ config(materialized='external_table') }}

CREATE TABLE IF NOT EXISTS {{ this }} (
    currency_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    currency_code TEXT NOT NULL UNIQUE,
    load_dttm TIMESTAMPTZ,
    load_id INT,
    source_id INT
)