{{ config(materialized='external_table') }}

CREATE TABLE IF NOT EXISTS {{ this }} (
    exchange_rate_id SERIAL PRIMARY KEY,
    file_path TEXT NOT NULL,
    currency_code TEXT NOT NULL,
    file_created_dttm TIMESTAMPTZ,
    file_updated_dttm TIMESTAMPTZ,
    exchange_date DATE,
    rate_usd NUMERIC,
    rate_eur NUMERIC,
    load_id INT
        REFERENCES {{ ref('loads') }} (load_id),
    UNIQUE (file_path, currency_code)
)