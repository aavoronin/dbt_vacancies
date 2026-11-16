{{ config(materialized='external_table') }}

CREATE TABLE IF NOT EXISTS {{ this }} (
    source_id SERIAL PRIMARY KEY,
    source_name TEXT NOT NULL UNIQUE,
    source_dttn TIMESTAMPTZ NOT NULL DEFAULT now()
)