{{ config(materialized='external_table') }}

CREATE TABLE IF NOT EXISTS {{ this }} (
    vacancy_id INT PRIMARY KEY,
    vacancy_id_name TEXT NOT NULL UNIQUE,
    load_dttm TIMESTAMPTZ,
    load_id INT,
    source_id INT
)