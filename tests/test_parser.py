import os
from dwh.ingestion.parser import ExcelParser
from dwh.ingestion.schemas import SCHEMAS

def test_parse_company_a_1():
    fixture_path = os.path.join("tests", "fixtures", "corporates_A_1.xlsm")
    with open(fixture_path, "rb") as f:
        content = f.read()

    parser = ExcelParser(schema=SCHEMAS["corporate_credit_rating"]["v1"])
    data = parser.parse(content, "corporates_A_1.xlsm")

    meta_eval = data["evaluations_metadata"]
    metrics = data["credit_metrics"]

    # 1. Metadata checks
    assert meta_eval["Rated entity"] == "Company A"
    assert meta_eval["CorporateSector"] == "Personal & Household Goods"
    assert meta_eval["Country of origin"] == "Federal Republic of Germany"
    assert meta_eval["Accounting principles"] == "IFRS"
    assert meta_eval["End of business year"] == "December"

    # 2. Methodologies checks
    assert "General Corporate Rating Methodology" in meta_eval["Rating methodologies applied"]
    assert "Consumer Products Rating Methodology" in meta_eval["Rating methodologies applied"]

    # 3. Industry Risks checks
    assert len(meta_eval["Industry risk"]) == 1
    assert meta_eval["Industry risk"][0] == "Consumer Products: Non-Discretionary"
    assert meta_eval["Industry risk score"][0] == "A"
    assert meta_eval["Industry weight"][0] == 1.0

    # 4. Evaluation checks
    assert meta_eval["Business risk profile"] == "B+"
    assert meta_eval["Financial risk profile"] == "C"
    assert meta_eval["Liquidity"] == "-2 notches"

    # 5. Credit Metrics checks
    years = metrics["[Scope Credit Metrics]"]
    idx_2024 = years.index(2024)
    idx_2025 = years.index("2025E")
    
    ebitda_cover = metrics["Scope-adjusted EBITDA interest cover"]
    assert ebitda_cover[idx_2024] == 36.79999999999997 or ebitda_cover[idx_2024] == 36.8
    assert ebitda_cover[idx_2025] == 36.79999999999997 or ebitda_cover[idx_2025] == 36.8
    
    # Check that Liquidity metric is present and distinct from the Liquidity evaluation
    assert isinstance(metrics["Liquidity"], list)
    assert len(metrics["Liquidity"]) == len(years)

    # 6. Validation check
    errors = parser.validate(data)
    assert len(errors) == 0

    # 7. Check parser and schema SHAs are calculated
    assert parser.schema_sha is not None
    assert len(parser.schema_sha) == 64
    assert parser.parser_sha is not None
    assert len(parser.parser_sha) == 64

def test_parse_company_b_1():
    fixture_path = os.path.join("tests", "fixtures", "corporates_B_1.xlsm")
    with open(fixture_path, "rb") as f:
        content = f.read()

    parser = ExcelParser(schema=SCHEMAS["corporate_credit_rating"]["v1"])
    data = parser.parse(content, "corporates_B_1.xlsm")

    meta_eval = data["evaluations_metadata"]

    # 1. Metadata checks
    assert meta_eval["Rated entity"] == "Company B"
    assert meta_eval["CorporateSector"] == "Automobiles & Parts"

    # 2. Industry Risks checks
    assert len(meta_eval["Industry risk"]) == 2
    # Verify weights
    assert "Automotive Suppliers" in meta_eval["Industry risk"]
    idx_supp = meta_eval["Industry risk"].index("Automotive Suppliers")
    assert meta_eval["Industry weight"][idx_supp] == 0.15
    assert meta_eval["Industry risk score"][idx_supp] == "BBB"

    assert "Automotive and Commercial Vehicle Manufacturers" in meta_eval["Industry risk"]
    idx_mfr = meta_eval["Industry risk"].index("Automotive and Commercial Vehicle Manufacturers")
    assert meta_eval["Industry weight"][idx_mfr] == 0.85
    assert meta_eval["Industry risk score"][idx_mfr] == "BB"

    # 3. Validation check
    errors = parser.validate(data)
    assert len(errors) == 0

def test_validation_fails_on_missing_required_keys():
    parser = ExcelParser(schema=SCHEMAS["corporate_credit_rating"]["v1"])
    bad_data = {
        "evaluations_metadata": {
            # "Rated entity" is missing!
            "CorporateSector": "Automobiles & Parts",
            "Segmentation criteria": "EBITDA",
            "Reporting Currency/Units": "EUR",
            "Country of origin": "Germany",
            "Accounting principles": "IFRS",
            "End of business year": "December",
            "Industry risk": ["Industry A"],
            "Industry risk score": ["A"],
            "Industry weight": [1.0]
        }
    }
    errors = parser.validate(bad_data)
    assert len(errors) > 0
    assert any("Missing required field: 'Rated entity' in section 'evaluations_metadata'" in err for err in errors)

def test_unexpected_cells_validation():
    mock_schema = {
        "schema_type": "mock",
        "schema_version": "v1",
        "sheet_name": "MASTER",
        "sections": {
            "evaluations_metadata": {
                "range": "C1:I34",
                "key_value": [
                    "Rated entity",
                    "CorporateSector",
                    "Segmentation criteria",
                    "Reporting Currency/Units",
                    "Country of origin",
                    "Accounting principles",
                    "End of business year"
                ],
                "optional_keys": []
            }
        }
    }
    parser = ExcelParser(schema=mock_schema)
    data = {
        "evaluations_metadata": {
            "Rated entity": "Company X",
            "CorporateSector": "Automobiles & Parts",
            "Segmentation criteria": "EBITDA",
            "Reporting Currency/Units": "EUR",
            "Country of origin": "Germany",
            "Accounting principles": "IFRS",
            "End of business year": "December",
            "Industry risk": ["Industry A"],
            "Industry risk score": ["A"],
            "Industry weight": [1.0]
        },
        "unexpected_cells": {
            "Z100": "stray comment",
            "A5": "unexpected header"
        }
    }
    errors = parser.validate(data)
    assert len(errors) == 2
    assert any("Unexpected data point found in cell Z100: 'stray comment'" in err for err in errors)
    assert any("Unexpected data point found in cell A5: 'unexpected header'" in err for err in errors)
