{{ config(materialized='external_table') }}

CREATE TABLE IF NOT EXISTS {{ this }} (
    certification_id INT PRIMARY KEY,
    certification_name TEXT NOT NULL UNIQUE,
    load_dttm TIMESTAMPTZ,
    load_id INT,
    source_id INT
)