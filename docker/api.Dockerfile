FROM python:3.13-slim

WORKDIR /app

# Install system utilities (postgresql-client for db connection checking)
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Astral uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# Copy pyproject.toml and uv.lock to install dependencies
COPY pyproject.toml uv.lock ./

# Create a virtual environment and prioritize its binaries in PATH
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

# Install project dependencies into the virtual environment
RUN uv pip install --no-cache-dir -r pyproject.toml --extra api


# Copy application source
COPY fast_api/ /app/fast_api/

# Expose FastAPI port
EXPOSE 8000

# Run Uvicorn with hot-reload enabled for development, watching only the fast_api directory
CMD ["uvicorn", "fast_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "fast_api"]
