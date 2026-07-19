{{ config(
    materialized='incremental',
    unique_key='upload_id'
) }}

WITH raw_data AS (
    SELECT 
        upload_id,
        parsed_at AS updated_at,
        parsed_payload->'_meta'->>'filename' AS filename,
        parsed_payload->'_meta'->>'parser_sha' AS parser_sha,
        parsed_payload->'_meta'->>'schema_sha' AS schema_sha,
        (parsed_payload->'_meta'->>'data_quality_passed')::boolean AS data_quality_passed,
        (
            SELECT COALESCE(SUM(CAST(val AS NUMERIC)), 0)
            FROM jsonb_array_elements_text(parsed_payload->'evaluations_metadata'->'Industry weight') AS val
        ) AS sum_industry_weights,
        parsed_payload
    FROM {{ source('ingestion', 'raw_corporate_credit_ratings') }}
    {% if is_incremental() %}
    WHERE parsed_at > (SELECT coalesce(max(updated_at), '1900-01-01'::timestamp) FROM {{ this }})
    {% endif %}
)
SELECT 
    upload_id,
    updated_at,
    filename,
    parser_sha,
    schema_sha,
    data_quality_passed,
    ABS(sum_industry_weights - 1.0) <= 1e-5 AS business_rules_passed,
    parsed_payload
FROM raw_data
