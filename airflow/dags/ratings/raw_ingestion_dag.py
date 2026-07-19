import os
import logging
from datetime import datetime, timedelta
from airflow.sdk import dag, task, Param

# Configure logging
logger = logging.getLogger(__name__)

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

@task
def scan_and_ingest_files(**context):
    """
    Scans the landing bucket or performs a manual backfill based on reprocess_pattern.
    Saves and parses spreadsheets dynamically using versioned idempotency.
    """
    from airflow.sdk import ObjectStoragePath
    from ratings.db_loader import load_excel_file, get_file_hash, check_already_processed
    from dwh.database import SessionLocal, init_db
    from dwh.ingestion.models import SourceFileAudit
    import re
    import fnmatch

    # Retrieve reprocess_pattern parameter if triggered manually
    dag_run = context.get("dag_run")
    conf = dag_run.conf if (dag_run and dag_run.conf) else {}
    reprocess_pattern = conf.get("reprocess_pattern")

    success_count = 0
    failure_count = 0

    init_db()

    if reprocess_pattern:
        logger.info(f"Manual backfill run requested for files matching pattern: '{reprocess_pattern}'")
        try:
            # Convert standard glob wildcard to regex pattern
            regex_str = fnmatch.translate(reprocess_pattern)
            pattern = re.compile(regex_str)
        except Exception as e:
            raise ValueError(f"Invalid wildcard pattern '{reprocess_pattern}': {str(e)}")

        landing_path = ObjectStoragePath("s3://landing", conn_id="aws_default")
        archive_path = ObjectStoragePath("s3://archive", conn_id="aws_default")

        # 1. Process matching files in the landing bucket first (if any)
        xlsm_files = [p for p in landing_path.iterdir() if p.name.endswith('.xlsm') and pattern.match(p.name)]
        logger.info(f"Found {len(xlsm_files)} matching files in landing bucket: {[p.name for p in xlsm_files]}")
        
        for file_path in xlsm_files:
            file_name = file_path.name
            logger.info(f"Processing landing file: {file_name}")
            try:
                content = file_path.read_bytes()
                file_hash = get_file_hash(content)
                dest_path = archive_path / f"{file_hash}_{file_name}"
                s3_path = str(dest_path)
                
                # Archive the file to S3
                dest_path.write_bytes(content)
                logger.info(f"Archived file to: {s3_path}")
                
                # Load into database (force reprocessing on manual trigger)
                load_excel_file(file_name, content, s3_path, force_reprocess=True)
                
                # Clean up from landing
                file_path.unlink()
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to process landing file '{file_name}': {str(e)}", exc_info=True)
                failure_count += 1

        # 2. Process matching files in the S3 archive bucket via database audit records
        db = SessionLocal()
        try:
            all_files = db.query(SourceFileAudit).all()
            matching_archived = [f for f in all_files if pattern.match(f.filename)]
        finally:
            db.close()

        logger.info(f"Found {len(matching_archived)} matching files in source file audits: {[f.filename for f in matching_archived]}")

        for file_rec in matching_archived:
            file_name = file_rec.filename
            s3_path = file_rec.s3_path
            logger.info(f"Checking archived file: '{file_name}' from path: '{s3_path}'")
            try:
                archive_file_path = ObjectStoragePath(s3_path, conn_id="aws_default")
                content = archive_file_path.read_bytes()
                # Load and parse (force reprocessing on manual trigger)
                load_excel_file(file_name, content, s3_path, force_reprocess=True)
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to reprocess archived file '{file_name}': {str(e)}", exc_info=True)
                failure_count += 1
    else:
        # Standard daily run
        landing_path = ObjectStoragePath("s3://landing", conn_id="aws_default")
        archive_path = ObjectStoragePath("s3://archive", conn_id="aws_default")

        # List all .xlsm files in the landing bucket
        xlsm_files = [p for p in landing_path.iterdir() if p.name.endswith('.xlsm')]
        logger.info(f"Found {len(xlsm_files)} files to process in landing: {[p.name for p in xlsm_files]}")

        for file_path in sorted(xlsm_files):
            file_name = file_path.name
            logger.info(f"Processing S3 object: {file_name}")
            
            try:
                content = file_path.read_bytes()
                file_hash = get_file_hash(content)
                dest_path = archive_path / f"{file_hash}_{file_name}"
                s3_path = str(dest_path)
                
                # Check versioned idempotency
                db = SessionLocal()
                skip_loading = False
                try:
                    existing = db.query(SourceFileAudit).filter(SourceFileAudit.file_hash == file_hash).first()
                    if existing:
                        from dwh.ingestion.parser import ExcelParser
                        from dwh.ingestion.schemas import SCHEMAS

                        parser = ExcelParser(schema=SCHEMAS["corporate_credit_rating"]["v1"])
                        try:
                            skip_loading = check_already_processed(db, existing.id, parser.parser_sha, parser.schema_sha, file_name)
                            if skip_loading:
                                file_path.unlink()
                                success_count += 1
                        except ValueError:
                            # File was previously processed but failed validation — retry it.
                            logger.warning(f"File '{file_name}' previously failed validation. It will be reprocessed.")
                            skip_loading = False
                finally:
                    db.close()

                if skip_loading:
                    continue
                
                # Upload to archive bucket in MinIO
                dest_path.write_bytes(content)
                logger.info(f"Archived file to: {s3_path}")
                
                # Load into database
                upload_id = load_excel_file(file_name, content, s3_path)
                logger.info(f"File '{file_name}' processed successfully. Reference ID: {upload_id}")
                
                # Delete from landing bucket
                file_path.unlink()
                success_count += 1
                
            except Exception as e:
                logger.error(f"Failed to process S3 object '{file_name}': {str(e)}", exc_info=True)
                failure_count += 1

    logger.info(f"Ingestion Run Complete: {success_count} succeeded, {failure_count} failed.")
    if failure_count > 0:
        raise ValueError(f"Ingestion task completed with {failure_count} failures.")


@dag(
    dag_id='raw_ratings_ingestion',
    default_args=default_args,
    description='Scans MinIO/S3 ratings-bucket and ingests raw rating xlsm spreadsheets into PostgreSQL',
    start_date=datetime(2026, 1, 1),
    schedule=None, # Run manually or triggered externally
    catchup=False,
    params={
        "reprocess_pattern": Param(
            default=None,
            type=["null", "string"],
            description="Wildcard pattern (e.g. 'corporates_A*' or 'corporates_A_1.xlsm') to reprocess archived/landing files. Leave blank for normal run."
        )
    },
    tags=['elt', 'ratings'],
)
def raw_ratings_ingestion_dag():
    from utils.dbt import dbt_task
    
    ingest_task = scan_and_ingest_files()
    dbt_run = dbt_task("dbt_run", command="run")
    dbt_test = dbt_task("dbt_test", command="test")
    
    ingest_task >> dbt_run >> dbt_test

# Instantiate the DAG
raw_ratings_ingestion_dag()
