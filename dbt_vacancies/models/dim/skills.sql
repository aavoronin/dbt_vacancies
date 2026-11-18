{{ config(materialized='external_table') }}

CREATE TABLE IF NOT EXISTS {{ this }} (
    skill_id INT PRIMARY KEY,
    skill_name TEXT NOT NULL UNIQUE,
    load_dttm TIMESTAMPTZ,
    load_id INT,
    source_id INT
)