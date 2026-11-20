{{ config(materialized='external_table') }}

CREATE TABLE IF NOT EXISTS {{ this }} (
    hiring_manager_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    hiring_manager_name TEXT NOT NULL UNIQUE,
    load_dttm TIMESTAMPTZ,
    load_id INT,
    source_id INT
)