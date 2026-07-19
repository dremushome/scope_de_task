# Data Warehouse Transformations (dbt)

Welcome to the transformation layer of our data pipeline! This directory contains all of our Data Build Tool (dbt) models.

If you are new to dbt or wondering why we chose to use it over traditional SQL scripts or Python Pandas transformations, here is a quick primer on the benefits it brings to our workflow.

## Why dbt? (The Value Proposition)

### 1. Analytics as Software Engineering
Traditionally, SQL was written as scattered, disconnected scripts. dbt brings software engineering best practices to data:
* **Modularity:** Instead of massive 1,000-line SQL scripts, logic is broken down into small, reusable components (models) like `staging`, `intermediate`, and `marts`.
* **Version Control:** All data transformations are represented as code (SQL) and stored in Git.
* **DRY Principle (Don't Repeat Yourself):** Through the use of `macros` and `refs`, we can reuse logic across multiple tables without copy-pasting.

### 2. Automatic Dependency Management
In a standard SQL pipeline, you have to manually define the execution order (e.g., "Run Table A, then Table B, then Table C"). 
With dbt, you simply use the `{{ ref('model_name') }}` function. dbt automatically analyzes these references to build a Directed Acyclic Graph (DAG) and executes the queries in the correct order, in parallel when possible!

### 3. Built-in Data Quality Testing
Bad data can break dashboards and erode trust. dbt allows us to write YAML configurations that test our data automatically:
* **Uniqueness:** Ensures a primary key is never duplicated.
* **Not Null:** Ensures critical columns never have missing values.
* **Accepted Values:** Ensures categorical columns only contain predefined strings.
* **Referential Integrity:** Ensures foreign keys match up.
If a test fails, the pipeline can alert us before the data reaches downstream consumers.

### 4. Auto-Generated Documentation
As you may have seen with the `dbt docs serve` command, dbt automatically generates a beautiful, interactive documentation website. 
* It parses our code to show a visual dependency graph (lineage).
* It pulls descriptions from our YAML files to document every column.
* It exposes the compiled SQL so anyone can see exactly how a metric was calculated.

### 5. Environment Separation
dbt allows us to safely test our code without breaking production. By using `profiles.yml` and targets (`dev`, `prod`), a developer can build models in their own personal isolated schema (`dev_alice`) before merging the code to build in the `marts` schema.

---

## How to explore our dbt project

To see these benefits in action, you can generate and serve the documentation site locally.

**Important Note:** The documentation server relies on a compiled `target/` directory. You must always run the `generate` command before the `serve` command!

Run this single command from the root of the repository:

```bash
cd dwh/dbt && uv run --env-file ../../.env dbt docs generate && uv run --env-file ../../.env dbt docs serve --port 8081
```

Once the server is running, open your browser to `http://localhost:8081` and click the green **View Lineage Graph** button in the bottom right corner to visually explore our pipeline!
