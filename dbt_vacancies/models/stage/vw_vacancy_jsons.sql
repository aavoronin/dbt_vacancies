{{ config(materialized='view') }}

SELECT
    vacancy_json_id,
    ("json"::json ->> 'saved_date')::TIMESTAMPTZ AS saved_date,
    ("json"::json ->> 'parsed_date')::TIMESTAMPTZ AS parsed_date,
    ("json"::json ->> 'parsing_version')::INT AS parsing_version,
    ("json"::json ->> 'vacancy_score')::NUMERIC AS vacancy_score,

    -- Priority: estimation2 (if model_id is valid)
    --        -> estimation1 (if model_id is valid)
    --        -> NULL
    -- Note: NULLIF handles both missing keys and explicit JSON "null" values.
    CASE
        WHEN NULLIF("json"::json -> 'estimation2' ->> 'model_id', 'null') IS NOT NULL
        THEN ("json"::json -> 'estimation2' ->> 'score')::NUMERIC

        WHEN NULLIF("json"::json -> 'estimation1' ->> 'model_id', 'null') IS NOT NULL
        THEN ("json"::json -> 'estimation1' ->> 'score')::NUMERIC

        ELSE NULL
    END AS score,

    CASE
        WHEN NULLIF("json"::json -> 'estimation2' ->> 'model_id', 'null') IS NOT NULL
        THEN ("json"::json -> 'estimation2' ->> 'score_percentile')::NUMERIC

        WHEN NULLIF("json"::json -> 'estimation1' ->> 'model_id', 'null') IS NOT NULL
        THEN ("json"::json -> 'estimation1' ->> 'score_percentile')::NUMERIC

        ELSE NULL
    END AS score_percentile,

    "json"::json,
    file_path,
    file_created_dttm,
    file_updated_dttm,
    load_id
FROM {{ ref('vacancy_jsons') }}