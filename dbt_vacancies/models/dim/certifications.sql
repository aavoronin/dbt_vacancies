CREATE TABLE IF NOT EXISTS {{ this }} (
    certification_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    certification_name TEXT NOT NULL UNIQUE,
    exam_code TEXT GENERATED ALWAYS AS (
        substring(certification_name from '([a-z]{2}-[0-9]{3})')
    ) STORED,
    load_dttm TIMESTAMPTZ,
    load_id INT,
    source_id INT
)