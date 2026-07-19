# Schemas defining Excel templates configurations and coordinates bounds

SCHEMAS = {
    "corporate_credit_rating": {
        "v1": {
            "schema_type": "corporate_credit_rating",
            "schema_version": "v1",
            "sheet_name": "MASTER",
            "sections": {
                # 1. Top Section of the sheet (preceding credit metrics)
                "evaluations_metadata": {
                    "range": "C1:I34",
                    "key_value": [
                        "Rated entity",
                        "CorporateSector",
                        "Segmentation criteria",
                        "Reporting Currency/Units",
                        "Country of origin",
                        "Accounting principles",
                        "End of business year",
                        "Business risk profile",
                        "(Blended) Industry risk profile",
                        "Competitive Positioning",
                        "Market share",
                        "Diversification",
                        "Operating profitability",
                        "Sector/company-specific factors (1)",
                        "Sector/company-specific factors (2)",
                        "Financial risk profile",
                        "Leverage",
                        "Interest cover",
                        "Cash flow cover",
                        "Liquidity"
                    ],
                    "named_list": [
                        "Rating methodologies applied",
                        "Industry risk",
                        "Industry risk score",
                        "Industry weight"
                    ],
                    "optional_keys": [
                        "Sector/company-specific factors (2)"
                    ]
                },
                # 2. Bottom Section of the sheet
                "credit_metrics": {
                    "range": "C35:M41",
                    "ignored_cell_values": {
                        "Locked": "M35:M41"
                    },
                    "key_value": [],
                    "named_list": [
                        "[Scope Credit Metrics]",
                        "Scope-adjusted EBITDA interest cover",
                        "Scope-adjusted debt/EBITDA",
                        "Scope-adjusted FFO/debt",
                        "Scope-adjusted loan/value",
                        "Scope-adjusted FOCF/debt",
                        "Liquidity"
                    ]
                }
            }
        }
    }
}
