WITH metrics AS (
    SELECT * FROM {{ ref('stg_corporate_financial_metrics') }}
),
ratings AS (
    SELECT * FROM {{ ref('stg_corporate_ratings') }}
)

SELECT
    m.rating_id,
    m.upload_id,
    r.company_name,
    r.corporate_sector,
    m.metric_name,
    m.metric_year,
    m.metric_year_str,
    m.metric_year_type,
    ROUND(m.metric_value_numeric, 4) AS metric_value_numeric,
    m.metric_value_text,
    m.updated_at
FROM metrics m
JOIN ratings r ON m.rating_id = r.id
