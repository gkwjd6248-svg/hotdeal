.PHONY: help setup dev-backend dev-frontend dev migrate seed test-backend test-frontend test lint clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ---- Setup ----

setup: ## Install all dependencies
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

# ---- Development ----

dev-backend: ## Start backend services via Docker Compose
	docker compose -f infra/docker-compose.yml up

dev-frontend: ## Start Next.js dev server
	cd frontend && npm run dev

dev: ## Start all services (backend + frontend) -- run in separate terminals
	@echo "Run 'make dev-backend' in one terminal and 'make dev-frontend' in another."

# ---- Database ----

migrate: ## Run Alembic migrations
	cd backend && alembic upgrade head

migrate-new: ## Create a new migration (usage: make migrate-new MSG="description")
	cd backend && alembic revision --autogenerate -m "$(MSG)"

seed: ## Seed initial data
	cd backend && python -m scripts.seed_shops
	cd backend && python -m scripts.seed_categories

# ---- Testing ----

test-backend: ## Run backend tests
	cd backend && pytest -v

test-frontend: ## Run frontend tests
	cd frontend && npm test

test: test-backend test-frontend ## Run all tests

# ---- Linting ----

lint: ## Lint both backend and frontend
	cd backend && ruff check . && ruff format --check .
	cd frontend && npm run lint

format: ## Auto-format code
	cd backend && ruff format .
	cd frontend && npm run format

# ---- Docker ----

docker-up: ## Start all Docker services
	docker compose -f infra/docker-compose.yml up -d

docker-down: ## Stop all Docker services
	docker compose -f infra/docker-compose.yml down

docker-logs: ## Tail Docker service logs
	docker compose -f infra/docker-compose.yml logs -f

docker-rebuild: ## Rebuild and restart Docker services
	docker compose -f infra/docker-compose.yml up -d --build

# ---- Cleanup ----

clean: ## Remove generated files
	find backend -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find backend -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf frontend/.next frontend/node_modules
