# Corporate Credit Rating Data Pipeline

A containerized, production-grade data pipeline that orchestrates the ingestion, validation, and dimensional modeling of corporate credit rating assessments from Excel files into a PostgreSQL data warehouse, exposing the resulting dataset through a FastAPI REST service.

---

## Project Structure

* **`dags/`**: Apache Airflow DAGs orchestrating the pipeline.
* **`tests/fixtures/`**: Repository-tracked sample rating files (`.xlsm`) used as test fixtures.
* **`.data/`**: Git-ignored runtime directory where the pipeline reads source files (bootstrapped from fixtures).
* **`config/` / `plugins/`**: Airflow configuration and plugin modules.
* **`Makefile` / `setup.sh`**: Environment bootstrapping and orchestration scripts.

---

## Quick Start & Local Setup

> [!IMPORTANT]
> The setup scripts (`setup.sh` and the `Makefile`) are specifically designed and tested for a **Linux VM / Linux environment** (e.g. Ubuntu, Debian, Fedora) running Docker.

A helper script and `Makefile` are provided to automate the local environment configuration (creating the `.env` file, verifying dependencies, and bootstrapping the data folder).

### 1. Bootstrapping the Environment

Run the setup using the `Makefile` (or run `setup.sh` directly if `make` is not yet installed on your host):

```bash
# Using the Makefile
make setup

# Or using the raw shell script directly
chmod +x setup.sh && ./setup.sh
```

This will automatically:
1. **Generate `.env`**: Creates the environment file from `.env.example`, setting the `AIRFLOW_UID` to your host's UID (preventing volume permission errors) and generating a cryptographically secure `FERNET_KEY`.
2. **Verify Dependencies**: Checks for the installation of Astral `uv`, Docker, and Docker Compose. If missing, it will attempt installation (via `apt`/`dnf` package managers) or guide you on manual setup.
3. **Seed Local Data**: Creates the local ignored `.data/` directory and copies the Excel sample files into it from `tests/fixtures/`.

---

## Commands Reference

### System Requirements
- **Docker & Docker Compose** installed
- **Memory**: The local Docker cluster actively consumes around **2GB of RAM** when idling (Airflow + MinIO + PostgreSQL + FastAPI). However, it is highly recommended to allocate **at least 4GB of RAM** to Docker to ensure stable operation during data ingestion peaks and to prevent Out-Of-Memory (OOM) kills.

Once your environment is bootstrapped, you can manage the containerized cluster using `make` commands:

| Command | Action | Description |
| :--- | :--- | :--- |
| `make setup` | `./setup.sh` | Performs initial environment checks, generates `.env`, and seeds the data folder. |
| `make up` | `docker compose up -d` | Starts the entire cluster (Airflow scheduler, worker, webserver, databases, etc.) in detached mode. |
| `make down` | `docker compose down` | Stops and removes running containers, networks, and services. |
| `make logs` | `docker compose logs -f` | Follows and displays real-time container log output. |
| `make build` | `docker compose build` | Rebuilds custom Airflow or API images defined in the docker services. |
| `make clean` | `rm -rf .data/*.xlsm` | Deletes the copied Excel assessment files from the local `.data/` folder. |

*Note: If you do not have `make` installed on your machine, you can run the equivalent commands directly (e.g., `docker compose up -d` or `./setup.sh`).*

---

## Local Services & Credentials

Once the cluster is up and running (`make up`), you can access the various services through your browser. 

Here are the default URLs and credentials configured via `setup.sh` and `docker-compose.yaml`:

| Service | URL | Username | Password | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Apache Airflow** | [http://localhost:8080](http://localhost:8080) | `airflow` | `airflow` | The DAG orchestration UI to trigger pipeline runs and monitor logs. |
| **MinIO Console** | [http://localhost:9001](http://localhost:9001) | `minioadmin` | `minioadmin` | S3-compatible object storage UI to browse raw files in the landing bucket. |
| **FastAPI Swagger** | [http://localhost:8000/docs](http://localhost:8000/docs) | *N/A* | *N/A* | Interactive Swagger UI to query the processed credit rating data. |
| **PostgreSQL (DWH)** | `localhost:5432` (DB: `dwh`) | `warehouse_user` | `warehouse_password` | The underlying data warehouse. Connect via a SQL client like DBeaver or DataGrip. |
| **dbt Docs** | [http://localhost:8081](http://localhost:8081) | *N/A* | *N/A* | Interactive data lineage graph. *Note: You must start this manually by running: `cd dwh/dbt && uv run --env-file ../../.env dbt docs generate && uv run --env-file ../../.env dbt docs serve --port 8081`* |

For more details on the transformation layer (dbt), please refer to the dedicated [dbt README](dwh/dbt/README.md).

---

## End-to-End Walkthrough

If this is your first time spinning up the project, follow these steps to see the entire pipeline in action:

1. **Bootstrap and Start the Cluster**
   From the root of the repository, initialize the environment and start the containers:
   ```bash
   make setup
   make up
   ```
   *Wait a few seconds for the containers (especially Airflow and PostgreSQL) to become healthy.*

2. **Seed the Landing Bucket**
   Before seeding, your MinIO buckets will be completely empty. Upload the test Excel files into the MinIO `landing` bucket:
   ```bash
   make seed
   ```
   *You can verify the files arrived by logging into the [MinIO Console](http://localhost:9001) using `minioadmin` / `minioadmin` and checking the `landing` bucket.*

3. **Run the Airflow DAG**
   - Open [Apache Airflow](http://localhost:8080) in your browser and log in with `airflow` / `airflow`.
   - You should see a DAG named `raw_ratings_ingestion`.
   - **Important:** Click the toggle switch next to the DAG name to **unpause** it first.
   - Click the **"Trigger DAG"** (play button) to start the run.
   - Click on the DAG to watch the tasks succeed in the Graph or Grid view as it ingests the files, parses them, and runs the `dbt` models.
   - **Check MinIO Again:** Once the DAG finishes, if you look back at MinIO, you will see the `landing` bucket is empty again, and all the files have been safely moved to the `archive` bucket!

4. **Query the Data API**
   Once the DAG completes successfully, the data is in the Data Warehouse.
   - Open the [FastAPI Swagger UI](http://localhost:8000/docs).
   - Try executing the `GET /snapshots/latest` endpoint to see the final, modeled credit ratings data served directly from the `marts.dim_corporate_ratings` table!
