{{ config(materialized='table') }}

WITH metrics AS (
    SELECT * FROM {{ ref('stg_corporate_financial_metrics') }}
)

SELECT
    upload_id,
    rating_id,
    MAX(metric_year) AS max_actual_year
FROM metrics
WHERE metric_year_type = 'Actual'
GROUP BY 
    upload_id,
    rating_id
