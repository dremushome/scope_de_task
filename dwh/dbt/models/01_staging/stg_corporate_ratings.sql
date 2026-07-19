{{ config(
    materialized='incremental',
    unique_key='id'
) }}

WITH raw_data AS (
    SELECT 
        id,
        upload_id,
        parsed_at AS updated_at,
        parsed_payload,
        (parsed_payload->'_meta'->>'data_quality_passed')::boolean AS data_quality_passed,
        (
            SELECT COALESCE(SUM(CAST(val AS NUMERIC)), 0)
            FROM jsonb_array_elements_text(parsed_payload->'evaluations_metadata'->'Industry weight') AS val
        ) AS sum_industry_weights
    FROM {{ source('ingestion', 'raw_corporate_credit_ratings') }}
    {% if is_incremental() %}
    WHERE parsed_at > (SELECT coalesce(max(updated_at), '1900-01-01'::timestamp) FROM {{ this }})
    {% endif %}
)
SELECT
    id,
    upload_id,
    updated_at,
    parsed_payload->'evaluations_metadata'->>'Rated entity' AS company_name,
    parsed_payload->'evaluations_metadata'->>'CorporateSector' AS corporate_sector,
    parsed_payload->'evaluations_metadata'->>'Accounting principles' AS accounting_principles,
    parsed_payload->'evaluations_metadata'->>'End of business year' AS end_of_business_year,
    parsed_payload->'evaluations_metadata'->>'Reporting Currency/Units' AS reporting_currency,
    parsed_payload->'evaluations_metadata'->>'Country of origin' AS country_of_origin,
    
    -- Additional String Metadata Fields
    parsed_payload->'evaluations_metadata'->>'Operating profitability' AS operating_profitability,
    parsed_payload->'evaluations_metadata'->>'Interest cover' AS interest_cover,
    parsed_payload->'evaluations_metadata'->>'Cash flow cover' AS cash_flow_cover,
    parsed_payload->'evaluations_metadata'->>'Business risk profile' AS business_risk_profile,
    parsed_payload->'evaluations_metadata'->>'Market share' AS market_share,
    parsed_payload->'evaluations_metadata'->>'Sector/company-specific factors (1)' AS sector_company_specific_factors_1,
    parsed_payload->'evaluations_metadata'->>'Sector/company-specific factors (2)' AS sector_company_specific_factors_2,
    parsed_payload->'evaluations_metadata'->>'Diversification' AS diversification,
    parsed_payload->'evaluations_metadata'->>'Leverage' AS leverage,
    parsed_payload->'evaluations_metadata'->>'Financial risk profile' AS financial_risk_profile,
    parsed_payload->'evaluations_metadata'->>'Segmentation criteria' AS segmentation_criteria,
    parsed_payload->'evaluations_metadata'->>'(Blended) Industry risk profile' AS blended_industry_risk_profile,
    parsed_payload->'evaluations_metadata'->>'Liquidity' AS liquidity,
    parsed_payload->'evaluations_metadata'->>'Competitive Positioning' AS competitive_positioning,
    
    -- Array Metadata Fields
    ARRAY(SELECT jsonb_array_elements_text(parsed_payload->'evaluations_metadata'->'Rating methodologies applied')) AS rating_methodologies_applied,
    ARRAY(SELECT jsonb_array_elements_text(parsed_payload->'evaluations_metadata'->'Industry risk')) AS industry_risk,
    ARRAY(SELECT jsonb_array_elements_text(parsed_payload->'evaluations_metadata'->'Industry risk score')) AS industry_risk_score,
    ARRAY(SELECT jsonb_array_elements_text(parsed_payload->'evaluations_metadata'->'Industry weight')) AS industry_weight,

    parsed_payload->'_meta'->>'filename' AS filename,
    parsed_payload->'_meta'->>'parser_sha' AS parser_sha,
    parsed_payload->'_meta'->>'schema_sha' AS schema_sha,
    parsed_payload
FROM raw_data
WHERE data_quality_passed = true
