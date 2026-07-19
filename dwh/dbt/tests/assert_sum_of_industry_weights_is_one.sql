-- Returns rows where the sum of industry risk weights is NOT equal to 1.0 (100%)
WITH unnested_weights AS (
    SELECT
        id,
        CAST(val AS NUMERIC) AS weight
    FROM {{ ref('stg_corporate_ratings') }},
    jsonb_array_elements_text(parsed_payload->'evaluations_metadata'->'Industry weight') AS val
),
aggregated_weights AS (
    SELECT
        id,
        SUM(weight) AS total_weight
    FROM unnested_weights
    GROUP BY id
)
SELECT
    id,
    total_weight
FROM aggregated_weights
WHERE ABS(total_weight - 1.0) > 1e-5
