{{ config(materialized='view') }}

SELECT 
    d.id,
    d.version_id,
    d.company_name,
    d.corporate_sector,
    d.country_of_origin,
    d.reporting_currency,
    d.business_risk_profile,
    d.financial_risk_profile,
    d.end_of_business_year,
    d.accounting_principles,
    d.sys_valid_from,
    d.sys_valid_to,
    d.is_system_current,
    d.is_latest_version_for_business_year,
    d.max_actual_year,
    COALESCE(
        jsonb_agg(
            jsonb_build_object(
                'name', f.metric_name,
                'value', f.metric_value_numeric,
                'text_value', f.metric_value_text,
                'year', f.metric_year,
                'year_type', f.metric_year_type
            )
        ) FILTER (WHERE f.metric_name IS NOT NULL), 
        '[]'::jsonb
    ) as metrics
FROM {{ ref('dim_corporate_ratings') }} d
LEFT JOIN {{ ref('fct_corporate_metrics') }} f ON d.id = f.rating_id
GROUP BY 
    d.id, 
    d.version_id, 
    d.company_name, 
    d.corporate_sector, 
    d.country_of_origin, 
    d.reporting_currency, 
    d.business_risk_profile, 
    d.financial_risk_profile, 
    d.end_of_business_year, 
    d.accounting_principles,
    d.sys_valid_from,
    d.sys_valid_to,
    d.is_system_current,
    d.is_latest_version_for_business_year,
    d.max_actual_year
