# Architectural Design Decisions

## 1. Dimensional Modeling vs. One Big Table (OBT)
**Decision:** We implemented a standard Star Schema (Normalized) instead of a One Big Table (OBT).
- **Context:** The task requires PostgreSQL. In a traditional row-oriented RDBMS like Postgres, repeating dimensional string values (like `company_name`, `corporate_sector`, `accounting_principles`) across every row of a metrics fact table causes significant database bloat and hurts query performance. By splitting these into `dim_companies_current` and `fct_corporate_metrics` and using joins, we optimize for Postgres.
- **Real-World Improvement:** In a modern columnar data warehouse (e.g., Snowflake, BigQuery, Redshift), disk is cheap and columnar dictionary compression easily handles repeated string values. In that scenario, we would denormalize the `fct_corporate_metrics` and the company dimensions into a single 'One Big Table' (OBT) to completely eliminate the overhead of `JOIN`s during querying.

## 2. Ingestion Naming Convention (`raw_` vs `stg_`)
**Decision:** We renamed the ingestion landing table from `stg_corporate_credit_ratings` to `raw_corporate_credit_ratings`.
- **Context:** The `stg_` prefix is universally reserved for the dbt staging layer (the first layer of analytics transformations). Using it for the ingestion landing table creates a confusing naming collision. Renaming it to `raw_` creates a clear boundary between the Data Engineering ingestion scripts and the Analytics Engineering dbt layer.

## 3. Slowly Changing Dimensions (SCD) & Bitemporal Modeling
**Decision:** We implemented a "Hybrid" Bitemporal SCD approach for determining the current state of a company in `dim_companies_current`.
- **Context:** If we strictly use the upload timestamp (`updated_at`) to define the "latest" record, an out-of-order upload (e.g., an analyst uploading a 2022 assessment *after* a 2023 assessment is already uploaded) would incorrectly overwrite the 2023 record as the current state of the company. 
- **Implementation:** We track two timelines. The ranking logic prioritizes the "Business Time" (the highest `metric_year` where type is 'Actual') first. It then uses "System Time" (the explicit file version, and finally `updated_at`) as tie-breakers. This ensures the "current" view is always the most recent financial statement, protecting against late-arriving historical data.

## 4. Surrogate Keys (`upload_id`)
**Decision:** We propagate the surrogate key `upload_id` all the way down into the final mart models.
- **Context:** While end-users may not query `upload_id`, propagating it to the marts ensures perfect lineage. If a data discrepancy is found in a dashboard, Data Engineers can use the `upload_id` to trace the metric back to the exact physical `.xlsm` file and the specific batch run that processed it in the `source_files_audit` table.

## 5. Metric Casting and Rounding
**Decision:** We preserve exact numeric precision in the staging layer and apply rounding in the presentation mart layer.
- **Context:** Excel files often introduce floating-point inaccuracies (e.g., `3.1400000000000001`). 
- **Implementation:** `stg_corporate_financial_metrics` safely casts the metrics to an unbounded `NUMERIC` to prevent any irreversible data loss. The rounding (`ROUND(..., 4)`) is applied purely in `fct_corporate_metrics`, ensuring BI tools receive clean numbers while the warehouse retains the pure raw data.
- **Why NUMERIC?** In PostgreSQL, calling `ROUND()` on a `NUMERIC` data type enforces standard "commercial rounding" (Round half away from zero: `2.5` -> `3`, `-2.5` -> `-3`). If we had cast it to a floating-point type like `DOUBLE PRECISION`, Postgres would default to the CPU's C-library rounding, which is often "Banker's Rounding" (Round half to even: `2.5` -> `2`, `3.5` -> `4`). By explicitly casting to `NUMERIC` in the staging layer, we guarantee mathematically consistent financial rounding regardless of the underlying server hardware.

## 6. Custom Database Schemas for dbt Layers
**Decision:** We configured `dbt_project.yml` to generate distinct database schemas (`staging`, `intermediate`, `marts`) instead of writing all tables to the default schema.
- **Context:** Using different schemas for different layers of the pipeline is a hallmark of a mature data platform.
- **Security & BI Cleanliness:** It allows for strict Role-Based Access Control (RBAC). End users and BI tools (like Tableau/Looker) are only granted `SELECT` access to the `marts` schema. They are completely insulated from the messy, rapidly changing `staging` and `intermediate` schemas, which are restricted to Data Engineering service accounts.

## 7. API Point-in-Time Parameters (`as_of_date` vs `business_year`)
**Decision:** We implemented two mutually exclusive query parameters for comparing companies: `as_of_date` (System Time) and `business_year` (Accounting Time).
- **Context:** In standard accounting, "As of Date" refers to the end of a financial period (e.g., Balance Sheet *as of* Dec 31). However, in Database Architecture and Data Warehousing (the domain of this assignment), `AS OF` is a reserved SQL keyword used for System-Time backtesting (e.g., "What did the database know *as of* this timestamp?").
- **Implementation:** To prevent future-sight bias for algorithmic backtesting, the `as_of_date` parameter queries the pure physical bitemporal audit trail (`sys_valid_from`). For traditional financial analysts wanting to compare Restated financials side-by-side, the `business_year` parameter queries the logical accounting timeline (`max_actual_year`). This design bridges the gap between Data Engineering precision and Business Analyst intuition.

## 8. API Endpoint Segmentation & Target Personas
**Decision:** The FastAPI application is split into three distinct routers (`/companies`, `/snapshots`, `/uploads`), each designed for a completely different user persona.
- **The `/companies` Router (For Financial Analysts & BI Tools):** This is the core business API. It presents the "Restated/Ultimate Truth" of a company's financial history. A Financial Analyst doesn't care that a metric was uploaded across 3 different Excel files; they just want to see the clean, deduplicated, year-over-year financial performance of the company.
- **The `/snapshots` Router (For Quants & System Auditors):** This endpoint exposes the raw, flat, bitemporal evaluation events. When a user queries by `from_date` and `to_date` here, it explicitly filters the **System Time** (`sys_valid_from`), answering questions like *"What data did the pipeline process in July?"*
- **The `/uploads` Router (For Data Engineers & Support):** This acts as the lowest-level lineage API. If a dashboard shows a suspicious metric, a Data Engineer can use this endpoint to fetch the exact physical `.xlsm` file directly from the MinIO archive, proving exactly what the client originally sent to the bank.

## 9. Future Production Enhancements
**Decision:** Certain enterprise-scale features were scoped out of the MVP but heavily considered for production readiness.
- **API Pagination:** The current list endpoints (e.g., `GET /uploads`, `GET /companies`) return raw unpaginated arrays. In a production environment with hundreds of thousands of rating iterations, this would cause FastAPI to run out of memory. The production implementation will wrap these array responses in a paginated envelope (e.g., `{"items": [...], "total": 100, "limit": 50, "offset": 0}`) and push the `LIMIT` and `OFFSET` clauses directly into the SQLAlchemy queries.
- **Strict Ingestion Validation (Option A):** Currently, basic range validations (e.g., weights must be between 0 and 1) are not enforced by the python parser. In production, we will adopt strict "front-door" validation by encoding boundary rules directly into the JSON schema configuration. The parser will automatically validate incoming data using `jsonschema`. Any file with out-of-bounds metrics will be strictly rejected (`data_quality_passed = false`), and the exact failure reason will be appended to the `data_quality_errors` array (which we already capture). This blocks garbage data from ever polluting the warehouse, while keeping the Python parser completely business-rule agnostic.

## 10. Database Role Management (Read-Only Users)
**Decision:** We deferred the creation of a read-only PostgreSQL role from the MVP setup scripts, but documented its necessity for production.
- **Context:** Currently, the `docker-compose.yaml` provisions a single `warehouse_user` that has full superuser privileges to run migrations, create schemas, and drop tables. If a downstream BI tool (like Metabase or Tableau) or an analyst using DBeaver connects with this user, they could accidentally mutate or drop core warehouse tables.
- **Production Pattern:** In a production setting, we would explicitly provision two distinct database roles:
  1. An `admin` or `etl_role` that the Airflow and FastAPI services use to write data.
  2. An `analyst_role` or `readonly_user` that is strictly granted read-only access. This enforces the Principle of Least Privilege, completely protecting the raw data and intermediate states while safely exposing the curated dimensional models.

## 11. Orchestration: Why Apache Airflow?
**Decision:** We chose Apache Airflow for orchestrating the ELT (Extract, Load, Transform) pipeline in tandem with dbt (data build tool).
- **Context:** In modern data architecture, we must first *extract and load* the raw data (via our Python ingestion scripts) before we *transform* it into clean, usable models (via our SQL-based `dbt` models). While a simple cron script could trigger this, Airflow natively supports DAGs (Directed Acyclic Graphs), allowing us to strictly orchestrate these dependencies. It ensures that the transformation steps (`dbt run` and `dbt test`) only execute after the data ingestion step has successfully completed. 
- **Idempotency & Visibility:** Airflow gives us a clear UI to monitor task states, view logs, and manually trigger backfills using parameters (like our `reprocess_pattern`). It's the industry standard for Python-based orchestrations.

## 12. Exponential Backoff Requirement
**Decision:** Exponential backoff on retries is handled natively by Airflow rather than implementing custom backoff logic in Python scripts.
- **Context:** The ingestion layer might experience transient errors (e.g. MinIO connection drops, Postgres lock timeouts). Implementing custom exponential backoff inside the task itself would hold up worker threads (e.g., using `time.sleep()`).
- **Implementation:** By leveraging Airflow's built-in parameters (`retry_exponential_backoff=True`, `retry_delay`, and `max_retry_delay`), Airflow automatically handles the backoff logic. If a task fails, Airflow releases the Celery worker and reschedules the task for the future (e.g. 1 min, 2 mins, 4 mins later). This allows workers to pick up other tasks in the meantime, resulting in a much more resilient and efficient distributed system.

## 13. Daily Batch Scheduling
**Decision:** The Airflow DAG is scheduled to run `@daily`.
- **Context:** Rather than triggering a pipeline run immediately upon every single file upload, running the pipeline daily allows financial analysts to upload multiple iterations or batches of rating sheets throughout the workday. The pipeline then picks up the entire batch at midnight, running the heavy `dbt` dimensional models just once per day to serve fresh data for the next morning. It can still be triggered manually on-demand if immediate processing is required.

## 15. Idempotency & Manual Backfilling
**Decision:** The ingestion pipeline is strictly idempotent by default, but supports targeted manual overrides.
- **Context:** If a file is uploaded multiple times without changes, reprocessing it wastes compute. However, if Data Engineering deploys a new version of the Python parser or updates the schema bounds, we need a way to easily "replay" historical files through the new logic.
- **Implementation:** By default, the `db_loader` checks a combination of the `upload_id`, `schema_sha`, and `parser_sha`. If the exact file was already processed with the exact same parser code and schema config, it is safely skipped. To trigger a backfill, a user can manually trigger the DAG in Airflow with a `reprocess_pattern` parameter (e.g., `*` or `corporates_A*`). The DAG will fetch the physical files from the MinIO archive bucket and force-reprocess them, automatically generating new dimension and fact records down the line.
