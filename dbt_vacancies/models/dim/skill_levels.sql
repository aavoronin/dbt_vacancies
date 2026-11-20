{{ config(materialized='external_table') }}

CREATE TABLE IF NOT EXISTS {{ this }} (
    skill_level_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    skill_level_name TEXT NOT NULL UNIQUE
)