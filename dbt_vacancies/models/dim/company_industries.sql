{{ config(materialized='external_table') }}

CREATE TABLE IF NOT EXISTS {{ this }} (
    company_industry_id INT PRIMARY KEY,
    company_industry_name TEXT NOT NULL UNIQUE,
    load_dttm TIMESTAMPTZ,
    load_id INT,
    source_id INT
)