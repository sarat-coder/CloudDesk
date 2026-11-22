UV ?= uv
PORT ?= 8000
TICKET ?= CD-1002

.PHONY: help setup backend seed ingest demo mcp test lint

help:
	@echo "CloudDesk development commands:"
	@echo "  make setup              Sync dependencies and create .env from .env.example if absent"
	@echo "  make backend            Run the FastAPI development server on port $(PORT)"
	@echo "  make seed               Load sample data into the local SQLite database"
	@echo "  make ingest             Chunk and index the knowledge base articles"
	@echo "  make demo               Run CD-1002 refund end-to-end (pauses for approval)"
	@echo "  make demo TICKET=CD-1005 Run a specific ticket end-to-end"
	@echo "  make mcp                Start the MCP server (read-only tools)"
	@echo "  make test               Run the offline pytest suite"
	@echo "  make lint               Run Ruff on backend and tests"

setup:
	$(UV) sync --group dev
	$(UV) run --group dev python -c "from pathlib import Path; example = Path('.env.example'); target = Path('.env'); target.write_text(example.read_text(encoding='utf-8'), encoding='utf-8') if not target.exists() else None"

backend:
	$(UV) run --group dev uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port $(PORT)

seed:
	PYTHONPATH=backend $(UV) run --group dev python -c "import asyncio; from app.core.database import create_tables; from app.services.seed_service import bootstrap_demo_data; asyncio.run(create_tables()); asyncio.run(bootstrap_demo_data())"

ingest:
	PYTHONPATH="backend:." $(UV) run --group dev python -c "import asyncio; from app.core.config import get_settings; from rag.ingest import run_ingest, build_fresh_retriever; s=get_settings(); n=asyncio.run(run_ingest(s, force=True)); print(f'Indexed {n} chunks from knowledge base')"

demo:
	PYTHONPATH="backend:." PYTHONIOENCODING=utf-8 $(UV) run --group dev python scripts/demo.py $(TICKET)

mcp:
	PYTHONPATH="backend:." $(UV) run --group dev python -m integrations.mcp.server

test:
	$(UV) run --group dev python -m pytest -q

lint:
	$(UV) run --group dev ruff check backend tests agents rag memory
