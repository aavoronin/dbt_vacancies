{{ config(materialized='external_table') }}

CREATE TABLE IF NOT EXISTS {{ this }} (
    language_id INT PRIMARY KEY,
    language_name TEXT NOT NULL UNIQUE,
    load_dttm TIMESTAMPTZ,
    load_id INT,
    source_id INT
)