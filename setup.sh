#!/bin/bash
set -e

echo "Starting setup..."

# 1. Create .env if not exists
if [ ! -f .env ]; then
    echo "Creating .env file..."
    if [ -f .env.example ]; then
        cp .env.example .env
        # Update AIRFLOW_UID
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' 's/AIRFLOW_UID=1000/AIRFLOW_UID='$(id -u)'/g' .env 2>/dev/null || true
        else
            sed -i 's/AIRFLOW_UID=1000/AIRFLOW_UID='$(id -u)'/g' .env 2>/dev/null || true
        fi
        # Generate FERNET_KEY
        NEW_KEY=$(python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())" 2>/dev/null || echo "EVUTFiPIdapyw8r8-L4v4VolSn1eB-s-amodgM1vpiA=")
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' 's|FERNET_KEY=.*|FERNET_KEY='$NEW_KEY'|g' .env 2>/dev/null || true
        else
            sed -i 's|FERNET_KEY=.*|FERNET_KEY='$NEW_KEY'|g' .env 2>/dev/null || true
        fi
        echo ".env created from .env.example with current UID and generated FERNET_KEY."
    else
        echo "AIRFLOW_UID=$(id -u)" > .env
        NEW_KEY=$(python3 -c 'import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())' 2>/dev/null || echo 'EVUTFiPIdapyw8r8-L4v4VolSn1eB-s-amodgM1vpiA=')
        echo "FERNET_KEY=$NEW_KEY" >> .env
        echo "AIRFLOW_WEB_PORT=8080" >> .env
        echo "WAREHOUSE_DB_USER=warehouse_user" >> .env
        echo "WAREHOUSE_DB_PASSWORD=warehouse_password" >> .env
        echo "WAREHOUSE_DB_NAME=dwh" >> .env
        echo "WAREHOUSE_DB_PORT=5432" >> .env
        echo "WAREHOUSE_DB_HOST=localhost" >> .env
        echo "MINIO_ROOT_USER=minioadmin" >> .env
        echo "MINIO_ROOT_PASSWORD=minioadmin" >> .env
        echo ".env created with default settings."
    fi
else
    echo ".env file already exists."
fi

# 2. Check and install uv
echo "Checking for uv..."
if ! command -v uv >/dev/null 2>&1; then
    echo "uv is not installed. Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo "uv installed successfully."
else
    echo "uv is already installed at $(which uv)."
fi

# 3. Check/Install Docker
echo "Checking for Docker..."
if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is not installed. Attempting installation..."
    if command -v apt-get >/dev/null 2>&1; then
        sudo apt-get update && sudo apt-get install -y docker.io
    elif command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y docker
    else
        echo "Could not detect package manager. Please install Docker manually."
        exit 1;
    fi
else
    echo "Docker is already installed ($(docker --version | head -n1))."
fi

# 4. Check/Install Docker Compose
echo "Checking for Docker Compose..."
if ! docker compose version >/dev/null 2>&1 && ! command -v docker-compose >/dev/null 2>&1; then
    echo "Docker Compose is not installed. Attempting to install..."
    if command -v apt-get >/dev/null 2>&1; then
        sudo apt-get update && sudo apt-get install -y docker-compose-v2
    elif command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y docker-compose
    else
        echo "Could not detect package manager. Please install Docker Compose manually."
        exit 1;
    fi
else
    echo "Docker Compose is already installed ($(docker compose version 2>/dev/null || docker-compose --version | head -n1))."
fi

# 5. Bootstrap data
echo "Bootstrapping data directory..."
mkdir -p .data/landing .data/archive
echo "Data directories created. Files will be bootstrapped via S3 API on startup."

echo "===================================================="
echo "Setup complete! You can now start the services."
echo "===================================================="
