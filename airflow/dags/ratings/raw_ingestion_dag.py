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
    'retries': 3,
    'retry_delay': timedelta(minutes=1),
    'retry_exponential_backoff': True,
    'max_retry_delay': timedelta(minutes=10),
}

@task
def scan_and_ingest_files(**context):
    """
    Scans the landing bucket or performs a manual backfill based on reprocess_pattern.
    Saves and parses spreadsheets dynamically using versioned idempotency.
    """
    from ratings.ingestion_logic import process_files

    # Retrieve reprocess_pattern parameter if triggered manually
    dag_run = context.get("dag_run")
    conf = dag_run.conf if (dag_run and dag_run.conf) else {}
    reprocess_pattern = conf.get("reprocess_pattern")

    process_files(reprocess_pattern)


@dag(
    dag_id='raw_ratings_ingestion',
    default_args=default_args,
    description='Scans MinIO/S3 ratings-bucket and ingests raw rating xlsm spreadsheets into PostgreSQL',
    start_date=datetime(2026, 1, 1),
    schedule='@daily',
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
