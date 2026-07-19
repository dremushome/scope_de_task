import os
import pytest
from dwh.database import SessionLocal, init_db, engine, Base
from dwh.ingestion.models import SourceFileAudit, RawCorporateCreditRating
from airflow.dags.ratings.db_loader import load_excel_file

@pytest.fixture(autouse=True)
def setup_db():
    # Ensure tables exist with the latest schema by dropping and recreating
    Base.metadata.drop_all(bind=engine)
    init_db()
    
    # Clean up existing rows in the DB to ensure a clean test
    db = SessionLocal()
    try:
        db.query(RawCorporateCreditRating).delete()
        db.query(SourceFileAudit).delete()
        db.commit()
    finally:
        db.close()

def test_db_loader_integration():

    # Load Company A_1
    path_a1 = os.path.join("tests", "fixtures", "corporates_A_1.xlsm")
    with open(path_a1, "rb") as f:
        content_a1 = f.read()

    id_a1 = load_excel_file(
        "corporates_A_1.xlsm",
        content_a1,
        "s3://ratings-bucket/archive/dummy_hash_corporates_A_1.xlsm"
    )
    assert id_a1 is not None

    # Load Company A_1 again (testing idempotency)
    id_a1_dup = load_excel_file(
        "corporates_A_1.xlsm",
        content_a1,
        "s3://ratings-bucket/archive/dummy_hash_corporates_A_1.xlsm"
    )
    assert id_a1_dup == id_a1

    # Load Company B_1
    path_b1 = os.path.join("tests", "fixtures", "corporates_B_1.xlsm")
    with open(path_b1, "rb") as f:
        content_b1 = f.read()

    id_b1 = load_excel_file(
        "corporates_B_1.xlsm",
        content_b1,
        "s3://ratings-bucket/archive/dummy_hash_corporates_B_1.xlsm"
    )
    assert id_b1 is not None
    assert id_b1 != id_a1

    # Validate database records
    db = SessionLocal()
    try:
        raw_count = db.query(SourceFileAudit).count()
        stg_count = db.query(RawCorporateCreditRating).count()
        assert raw_count == 2
        assert stg_count == 2

        # Verify SourceFileAudit S3 path
        a1_raw = db.query(SourceFileAudit).filter(SourceFileAudit.id == id_a1).first()
        assert a1_raw is not None
        assert a1_raw.s3_path == "s3://ratings-bucket/archive/dummy_hash_corporates_A_1.xlsm"

        # Verify JSONB payload details in database
        a1_parsed = db.query(RawCorporateCreditRating).filter(RawCorporateCreditRating.upload_id == id_a1).first()
        assert a1_parsed is not None
        assert a1_parsed.parsed_payload["evaluations_metadata"]["Rated entity"] == "Company A"

        # Verify meta audit fields and flat data quality fields
        meta = a1_parsed.parsed_payload["_meta"]
        assert meta["filename"] == "corporates_A_1.xlsm"
        assert meta["schema_type"] == "corporate_credit_rating"
        assert meta["schema_version"] == "v1"
        assert len(meta["schema_sha"]) == 64
        assert len(meta["parser_sha"]) == 64
        assert meta["data_quality_passed"] is True
        assert len(meta["data_quality_errors"]) == 0

        b1_parsed = db.query(RawCorporateCreditRating).filter(RawCorporateCreditRating.upload_id == id_b1).first()
        assert b1_parsed is not None
        assert b1_parsed.parsed_payload["evaluations_metadata"]["Rated entity"] == "Company B"
    finally:
        db.close()

def test_db_loader_fails_on_validation():
    # Load Company A_1, but modify it to fail validation (unexpected cell)
    # We will write a modified xlsx to memory to create an unexpected cell
    import openpyxl
    import io
    
    path_a1 = os.path.join("tests", "fixtures", "corporates_A_1.xlsm")
    wb = openpyxl.load_workbook(path_a1)
    sheet = wb["MASTER"]
    # Write unexpected cell
    sheet["Z100"] = "unexpected_noise"
    
    out = io.BytesIO()
    wb.save(out)
    bad_content = out.getvalue()

    # Ingest the bad file: should raise ValueError
    with pytest.raises(ValueError) as excinfo:
        load_excel_file(
            "bad_corporates.xlsm",
            bad_content,
            "s3://ratings-bucket/archive/bad_hash_corporates.xlsm"
        )
    assert "Validation failed" in str(excinfo.value)
    assert "Z100" in str(excinfo.value)

    # Verify that SourceFileAudit and RawCorporateCreditRating rows exist for failed file, and data_quality_passed is False
    db = SessionLocal()
    try:
        raw_rec = db.query(SourceFileAudit).filter(SourceFileAudit.filename == "bad_corporates.xlsm").first()
        assert raw_rec is not None
        
        parsed_rec = db.query(RawCorporateCreditRating).filter(RawCorporateCreditRating.upload_id == raw_rec.id).first()
        assert parsed_rec is not None
        
        meta = parsed_rec.parsed_payload["_meta"]
        assert meta["data_quality_passed"] is False
        assert any("Z100" in err for err in meta["data_quality_errors"])
    finally:
        db.close()
