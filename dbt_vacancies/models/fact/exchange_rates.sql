{{ config(materialized='external_table') }}

CREATE TABLE IF NOT EXISTS {{ this }} (
    exchange_rate_fact_id BIGINT GENERATED ALWAYS AS IDENTITY,
    date_id INT,
    currency_id INT,
    rate_usd NUMERIC,
    rate_eur NUMERIC,
    load_dttm TIMESTAMPTZ,
    load_id INT,
    source_id INT,
    partition_key INT,
    modified_timestamp TIMESTAMPTZ,
    version INT,
    PRIMARY KEY (partition_key, exchange_rate_fact_id),
    UNIQUE (partition_key, date_id, currency_id)
) PARTITION BY RANGE (partition_key)