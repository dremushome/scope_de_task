import hashlib
import logging
from sqlalchemy.orm import Session
from dwh.database import SessionLocal, init_db
from dwh.ingestion.models import SourceFileAudit, RawCorporateCreditRating
from dwh.ingestion.parser import ExcelParser
from dwh.ingestion.schemas import SCHEMAS

logger = logging.getLogger(__name__)

def get_file_hash(binary_content: bytes) -> str:
    """Computes the SHA-256 checksum of a byte stream."""
    return hashlib.sha256(binary_content).hexdigest()

def check_already_processed(db: Session, upload_id: int, current_parser_sha: str, current_schema_sha: str, filename: str) -> bool:
    """Returns True if skipped, False otherwise. Raises ValueError if previous run failed validation."""
    existing_record = db.query(RawCorporateCreditRating).filter(
        RawCorporateCreditRating.upload_id == upload_id,
        RawCorporateCreditRating.parsed_payload[('_meta', 'parser_sha')].astext == current_parser_sha,
        RawCorporateCreditRating.parsed_payload[('_meta', 'schema_sha')].astext == current_schema_sha
    ).first()

    if existing_record:
        logger.info(f"File '{filename}' (Upload ID: {upload_id}) has already been processed with parser {current_parser_sha} and schema {current_schema_sha}. Skipping parsing.")
        passed = existing_record.parsed_payload.get("_meta", {}).get("data_quality_passed", False)
        if not passed:
            errors_str = "; ".join(existing_record.parsed_payload.get("_meta", {}).get("data_quality_errors", []))
            raise ValueError(f"Validation previously failed for spreadsheet '{filename}': {errors_str}")
        return True
    return False

def load_excel_file(filename: str, binary_content: bytes, s3_path: str, force_reprocess: bool = False) -> int:
    """
    Ingests an Excel file:
      1. Computes the SHA-256 hash.
      2. Ensures the SourceFileAudit record exists.
      3. Performs versioned idempotency check (unless force_reprocess is True).
      4. Parses and validates using ExcelParser.
      5. Saves the parsed payload directly to raw_corporate_credit_ratings.
      6. Commits transaction and then raises ValueError if validation fails (to fail DAG task).
    """

    file_hash = get_file_hash(binary_content)
    db = SessionLocal()
    try:
        # Step 1: Ensure SourceFileAudit record exists
        raw_upload = db.query(SourceFileAudit).filter(SourceFileAudit.file_hash == file_hash).first()
        if not raw_upload:
            raw_upload = SourceFileAudit(
                filename=filename,
                file_hash=file_hash,
                s3_path=s3_path
            )
            db.add(raw_upload)
            db.commit()
            db.refresh(raw_upload)
        
        upload_id = raw_upload.id

        # Step 2: Initialize parser
        parser = ExcelParser(schema=SCHEMAS["corporate_credit_rating"]["v1"])
        current_parser_sha = parser.parser_sha
        current_schema_sha = parser.schema_sha

        # Step 3: Perform Versioned Idempotency Check (if not forced)
        if not force_reprocess:
            if check_already_processed(db, upload_id, current_parser_sha, current_schema_sha, filename):
                return upload_id
        # Step 4: Parse the spreadsheet and generate validation metadata
        parsed_payload = parser.parse(binary_content, filename)
        passed = parsed_payload["_meta"]["data_quality_passed"]
        validation_errors = parsed_payload["_meta"]["data_quality_errors"]

        # Step 5: Store parsed staging JSON record (even on validation failure)
        stg_rating = RawCorporateCreditRating(
            upload_id=upload_id,
            parsed_payload=parsed_payload
        )
        db.add(stg_rating)
        db.commit()

    except Exception as e:
        db.rollback()
        logger.error(f"Error during ingestion of '{filename}': {str(e)}")
        raise
    finally:
        db.close()

    # Step 6: Fail the Airflow task if the validation failed
    if not passed:
        error_str = "; ".join(validation_errors)
        raise ValueError(f"Validation failed for spreadsheet '{filename}': {error_str}")

    logger.info(f"Successfully ingested and parsed '{filename}' (Upload ID: {upload_id}).")
    return upload_id
