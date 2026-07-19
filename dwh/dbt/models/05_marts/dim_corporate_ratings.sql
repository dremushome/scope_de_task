{{ config(materialized='table') }}

WITH ratings AS (
    SELECT * FROM {{ ref('stg_corporate_ratings') }}
),
max_years AS (
    SELECT * FROM {{ ref('int_upload_max_years') }}
),
joined_ratings AS (
    SELECT 
        r.*,
        m.max_actual_year
    FROM ratings r
    LEFT JOIN max_years m ON r.upload_id = m.upload_id AND r.id = m.rating_id
),
history_ratings AS (
    SELECT
        *,
        updated_at AS sys_valid_from,
        LEAD(updated_at) OVER (
            PARTITION BY company_name 
            ORDER BY updated_at ASC
        ) AS sys_valid_to,
        (ROW_NUMBER() OVER (
            PARTITION BY company_name, max_actual_year 
            ORDER BY 
                COALESCE(
                    CAST(
                        NULLIF(
                            REGEXP_REPLACE(filename, '^.*_([0-9]+)\.[a-zA-Z]+$', '\1'),
                            filename
                        ) AS INTEGER
                    ),
                    1
                ) DESC,
                updated_at DESC
        ) = 1) AS is_latest_version_for_business_year,
        CAST(
            NULLIF(
                REGEXP_REPLACE(filename, '^.*_([0-9]+)\.[a-zA-Z]+$', '\1'),
                filename
            ) AS INTEGER
        ) AS version_id
    FROM joined_ratings
)
SELECT
    id,
    upload_id,
    company_name,
    corporate_sector,
    accounting_principles,
    end_of_business_year,
    reporting_currency,
    country_of_origin,
    operating_profitability,
    interest_cover,
    cash_flow_cover,
    business_risk_profile,
    market_share,
    sector_company_specific_factors_1,
    sector_company_specific_factors_2,
    diversification,
    leverage,
    financial_risk_profile,
    segmentation_criteria,
    blended_industry_risk_profile,
    liquidity,
    competitive_positioning,
    rating_methodologies_applied,
    industry_risk,
    industry_risk_score,
    industry_weight,
    filename,
    parser_sha,
    schema_sha,
    sys_valid_from,
    sys_valid_to,
    (sys_valid_to IS NULL) AS is_system_current,
    is_latest_version_for_business_year,
    max_actual_year,
    version_id
FROM history_ratings
