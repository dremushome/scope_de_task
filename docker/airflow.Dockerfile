FROM apache/airflow:3.3.0-python3.13

# Copy pyproject.toml and uv.lock to install pipeline extras
COPY pyproject.toml uv.lock ./

# Install core and pipeline dependencies using the built-in uv package manager
RUN uv pip install --no-cache-dir -r pyproject.toml --extra pipeline
