.PHONY: help setup up down build clean logs

# Default target
all: help

help:
	@echo "Available commands:"
	@echo "  setup            - Complete setup (create .env, install uv, check docker/compose, bootstrap data)"
	@echo "  up               - Run docker compose up -d"
	@echo "  seed             - Upload sample data files to MinIO landing bucket"
	@echo "  down             - Run docker compose down"
	@echo "  logs             - View running container logs (tail/follow)"
	@echo "  build            - Build docker compose services"
	@echo "  clean            - Clean local .data/ folder"

setup:
	@chmod +x setup.sh
	@./setup.sh

up:
	docker compose up --build -d

seed:
	uv run bootstrap_minio.py

down:
	docker compose down

logs:
	docker compose logs -f

build:
	docker compose build

clean:
	@echo "Cleaning up local data directory..."
	rm -rf .data/*
	@echo "Clean complete."
