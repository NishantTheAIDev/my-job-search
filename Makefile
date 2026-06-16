# Job Search Assistant — common dev tasks.
# Run `make` or `make help` to list targets.

# Use bash and run all lines of a recipe in one shell.
SHELL := /bin/bash
.ONESHELL:

# Default Alembic revision message; override: make migrate-new m="add x"
m ?= migration

.DEFAULT_GOAL := help

.PHONY: help install db-up db-down db-logs db-shell migrate migrate-new migrate-down \
        start run dev backend frontend test test-backend test-frontend \
        lint lint-fix format build check setup clean

help: ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

# --- Setup ------------------------------------------------------------------

install: ## Install backend (uv) and frontend (npm) dependencies
	uv sync --extra dev
	cd frontend && npm install

setup: install db-up migrate ## Full first-time setup: deps + Postgres + migrations
	@echo "Setup complete. Run 'make dev' (frontend) and 'make run' (backend)."

# --- Database (Docker Postgres + Alembic) -----------------------------------

db-up: ## Start the Postgres container (Docker)
	docker compose up -d postgres

db-down: ## Stop the Postgres container
	docker compose down

db-logs: ## Tail Postgres container logs
	docker compose logs -f postgres

db-shell: ## Open a psql shell in the Postgres container
	docker exec -it jobsearch-postgres psql -U jobsearch -d jobsearch

migrate: ## Apply all pending Alembic migrations
	uv run alembic upgrade head

migrate-new: ## Autogenerate a migration: make migrate-new m="message"
	uv run alembic revision --autogenerate -m "$(m)"

migrate-down: ## Roll back the most recent migration
	uv run alembic downgrade -1

# --- Run --------------------------------------------------------------------

start: db-up ## Start backend (:8000) AND frontend (:5173) together; Ctrl-C stops both
	@echo "Starting backend (:8000) and frontend (:5173) — press Ctrl-C to stop both."
	@trap 'kill 0' EXIT INT TERM; \
	uv run main.py & \
	( cd frontend && npm run dev ) & \
	wait

run: ## Start the FastAPI backend on :8000 (reload)
	uv run main.py

backend: run ## Alias for `run`

dev: ## Start the Vite frontend dev server on :5173
	cd frontend && npm run dev

frontend: dev ## Alias for `dev`

# --- Test / quality ---------------------------------------------------------

test: test-backend test-frontend ## Run all backend + frontend tests

test-backend: ## Run backend tests (pytest)
	uv run pytest

test-frontend: ## Run frontend tests once (vitest)
	cd frontend && npx vitest run

lint: ## Lint backend (ruff) and frontend (eslint)
	uv run ruff check .
	cd frontend && npm run lint

lint-fix: ## Auto-fix backend lint issues
	uv run ruff check --fix .

format: ## Format backend code (ruff)
	uv run ruff format .

build: ## Type-check + production build of the frontend
	cd frontend && npm run build

check: lint test build ## Lint, test, and build everything (pre-push gate)

# --- Cleanup ----------------------------------------------------------------

clean: ## Remove Python caches and the frontend build output
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf frontend/dist .pytest_cache
