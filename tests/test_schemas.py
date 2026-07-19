import pytest
from openpyxl.utils import range_boundaries
from dwh.ingestion.schemas import SCHEMAS

def validate_excel_range(range_str: str, context: str):
    try:
        min_c, min_r, max_c, max_r = range_boundaries(range_str)
        assert min_c <= max_c, f"Invalid column order in range '{range_str}' for {context}"
        assert min_r <= max_r, f"Invalid row order in range '{range_str}' for {context}"
    except Exception as e:
        pytest.fail(f"Invalid Excel range string format '{range_str}' for {context}: {str(e)}")

def test_schema_registry_validation():
    """
    Validates that all configured schemas in the registry are structurally sound
    and follow the schema definition specifications.
    """
    assert isinstance(SCHEMAS, dict), "SCHEMAS must be a dictionary"
    assert len(SCHEMAS) > 0, "SCHEMAS registry must not be empty"

    for rating_type, versions in SCHEMAS.items():
        assert isinstance(versions, dict), f"Versions for '{rating_type}' must be a dictionary"
        assert len(versions) > 0, f"Rating type '{rating_type}' must have at least one version defined"
        
        for version, config in versions.items():
            context = f"[{rating_type}][{version}]"
            
            # 1. Validate sheet_name is present and is a string
            assert "sheet_name" in config, f"Missing 'sheet_name' in {context}"
            assert isinstance(config["sheet_name"], str) and config["sheet_name"].strip() != "", f"'sheet_name' must be a non-empty string in {context}"
            
            # 2. Validate sections is present and is a dictionary
            assert "sections" in config, f"Missing 'sections' in {context}"
            assert isinstance(config["sections"], dict), f"'sections' must be a dictionary in {context}"
            assert len(config["sections"]) > 0, f"'sections' must not be empty in {context}"
            
            for section_name, section_cfg in config["sections"].items():
                sec_context = f"{context} -> section '{section_name}'"
                
                # 3. Validate range string
                assert "range" in section_cfg, f"Missing 'range' in {sec_context}"
                assert isinstance(section_cfg["range"], str), f"'range' must be a string in {sec_context}"
                validate_excel_range(section_cfg["range"], sec_context)
                
                # 4. Validate key_value list
                assert "key_value" in section_cfg, f"Missing 'key_value' in {sec_context}"
                assert isinstance(section_cfg["key_value"], list), f"'key_value' must be a list in {sec_context}"
                for item in section_cfg["key_value"]:
                    assert isinstance(item, str) and item.strip() != "", f"All items in 'key_value' must be non-empty strings in {sec_context}"
                
                # 5. Validate named_list list
                assert "named_list" in section_cfg, f"Missing 'named_list' in {sec_context}"
                assert isinstance(section_cfg["named_list"], list), f"'named_list' must be a list in {sec_context}"
                for item in section_cfg["named_list"]:
                    assert isinstance(item, str) and item.strip() != "", f"All items in 'named_list' must be non-empty strings in {sec_context}"
                    
                # 6. Validate optional ignored_cell_values
                if "ignored_cell_values" in section_cfg:
                    ignored_cells = section_cfg["ignored_cell_values"]
                    assert isinstance(ignored_cells, dict), f"'ignored_cell_values' must be a dictionary in {sec_context}"
                    for val_str, val_range in ignored_cells.items():
                        assert isinstance(val_str, str) and val_str.strip() != "", f"Ignored cell value key must be a non-empty string in {sec_context}"
                        assert isinstance(val_range, str), f"Ignored cell range must be a string in {sec_context}"
                        validate_excel_range(val_range, f"{sec_context} -> ignored cell '{val_str}'")
