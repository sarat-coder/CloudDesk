UV ?= uv
PORT ?= 8000

.PHONY: help setup backend seed test lint

help:
	@echo "CloudDesk development commands:"
	@echo "  make setup   Sync dependencies and create .env from .env.example if absent"
	@echo "  make backend Run the FastAPI development server on port $(PORT)"
	@echo "  make seed    Load sample data into the local SQLite database"
	@echo "  make test    Run the offline pytest suite"
	@echo "  make lint    Run Ruff on backend and tests"

setup:
	$(UV) sync --group dev
	$(UV) run --group dev python -c "from pathlib import Path; example = Path('.env.example'); target = Path('.env'); target.write_text(example.read_text(encoding='utf-8'), encoding='utf-8') if not target.exists() else None"

backend:
	$(UV) run --group dev uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port $(PORT)

seed:
	PYTHONPATH=backend $(UV) run --group dev python -c "import asyncio; from app.core.database import create_tables; from app.services.seed_service import bootstrap_demo_data; asyncio.run(create_tables()); asyncio.run(bootstrap_demo_data())"

test:
	$(UV) run --group dev python -m pytest -q

lint:
	$(UV) run --group dev ruff check backend tests
