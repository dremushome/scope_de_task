{{ config(
    materialized='incremental',
    unique_key=['rating_id', 'metric_name', 'year_idx']
) }}

WITH raw_data AS (
    SELECT 
        id AS rating_id,
        upload_id,
        parsed_at AS updated_at,
        parsed_payload
    FROM {{ source('ingestion', 'raw_corporate_credit_ratings') }}
    WHERE (parsed_payload->'_meta'->>'data_quality_passed')::boolean = true
    {% if is_incremental() %}
      AND parsed_at > (SELECT coalesce(max(updated_at), '1900-01-01'::timestamp) FROM {{ this }})
    {% endif %}
),
-- Extract the year array and unnest it with ordinality
years AS (
    SELECT 
        rating_id,
        value::text AS year_str,
        ordinality AS year_idx
    FROM raw_data,
    jsonb_array_elements_text(parsed_payload->'credit_metrics'->'[Scope Credit Metrics]') WITH ORDINALITY AS arr(value, ordinality)
),
-- Extract all other metrics and unnest their arrays with ordinality
metrics AS (
    SELECT 
        r.rating_id,
        m.key AS metric_name,
        val::text AS metric_val,
        ordinality AS year_idx
    FROM raw_data r,
    jsonb_each(r.parsed_payload->'credit_metrics') AS m,
    jsonb_array_elements_text(m.value) WITH ORDINALITY AS arr(val, ordinality)
    WHERE m.key != '[Scope Credit Metrics]'
)
SELECT
    m.rating_id,
    r.upload_id,
    r.updated_at,
    m.metric_name,
    m.year_idx,
    CAST(SUBSTRING(y.year_str FROM '^[0-9]+') AS INTEGER) AS metric_year,
    y.year_str AS metric_year_str,
    CASE
        WHEN TRIM(y.year_str) ~ '^[0-9]{4}$' OR TRIM(y.year_str) LIKE '%A' THEN 'Actual'
        WHEN TRIM(y.year_str) LIKE '%E' THEN 'Estimate'
        WHEN TRIM(y.year_str) LIKE '%P' THEN 'Pro-forma'
        WHEN TRIM(y.year_str) LIKE '%R' THEN 'Restated'
        WHEN TRIM(y.year_str) LIKE '%F' THEN 'Forecast'
        ELSE 'Unknown'
    END AS metric_year_type,
    -- Safely cast metric value to numeric (nullify blank or non-numeric values like 'n.a.')
    CASE 
        WHEN m.metric_val ~ '^-?[0-9]+(\.[0-9]+)?$' THEN CAST(m.metric_val AS NUMERIC)
        ELSE NULL
    END AS metric_value_numeric,
    m.metric_val AS metric_value_text
FROM metrics m
JOIN years y ON m.rating_id = y.rating_id AND m.year_idx = y.year_idx
JOIN raw_data r ON m.rating_id = r.rating_id
