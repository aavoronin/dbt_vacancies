{{ config(materialized='external_table') }}

CREATE TABLE IF NOT EXISTS {{ this }} (
    load_id SERIAL PRIMARY KEY,
    load_dttm TIMESTAMPTZ NOT NULL DEFAULT now(),
    source_id INT NOT NULL
        REFERENCES {{ ref('sources') }} (source_id)
)