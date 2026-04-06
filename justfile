# Default recipe - show available commands
default:
    @just --list

# =============================================================================
# Setup
# =============================================================================

# Initial project setup — one command to get going
setup:
    @echo "Setting up orbital-takehome..."
    @cp -n .env.example .env 2>/dev/null || true
    @mkdir -p uploads
    docker compose build
    @echo ""
    @echo "Setup complete! Next steps:"
    @echo "  1. Edit .env with your Anthropic API key"
    @echo "  2. Run 'just dev' to start everything"

# =============================================================================
# Development
# =============================================================================

# Start the full stack (Postgres, backend, frontend) with hot reload
dev:
    docker compose up

# Start in background
dev-detach:
    docker compose up -d

# Stop all services
stop:
    docker compose down

# Stop all services and remove database volume
reset:
    docker compose down -v
    @echo "All data cleared. Run 'just dev' to start fresh."

# View backend logs
logs-backend:
    docker compose logs -f backend

# View all logs
logs:
    docker compose logs -f

# =============================================================================
# Database
# =============================================================================

# Initialize / migrate database
db-init:
    docker compose exec backend uv run alembic upgrade head
    @echo "Database initialised!"

# Create a new migration
db-migrate message:
    docker compose exec backend uv run alembic revision --autogenerate -m "{{message}}"

# Apply pending migrations
db-upgrade:
    docker compose exec backend uv run alembic upgrade head

# Open psql shell
db-shell:
    docker compose exec db psql -U orbital orbital_takehome

# =============================================================================
# Testing
# =============================================================================

# Run backend tests
test *args:
    docker compose exec backend uv run pytest {{args}}

# Run backend tests with verbose output
test-v *args:
    docker compose exec backend uv run pytest -v {{args}}

# =============================================================================
# Code Quality (runs locally, not in Docker)
# =============================================================================

# Run all checks (lint + typecheck)
check: check-backend check-frontend

# Run all checks + tests
verify: check test

# Format all code
fmt: fmt-backend fmt-frontend

# Python checks
check-backend:
    docker compose exec backend uv run ruff check backend/src
    docker compose exec backend uv run pyright backend/src

# Format Python
fmt-backend:
    docker compose exec backend uv run ruff format backend/src
    docker compose exec backend uv run ruff check --fix backend/src

# Frontend checks
check-frontend:
    cd frontend && npx @biomejs/biome check ./src && npx tsc --noEmit

# Format frontend
fmt-frontend:
    cd frontend && npx @biomejs/biome format --write ./src

# =============================================================================
# Utilities
# =============================================================================

# Shell into backend container
shell-backend:
    docker compose exec backend bash

# Shell into frontend container
shell-frontend:
    docker compose exec frontend bash

# Install a new Python dependency
add-dep package:
    docker compose exec backend uv add {{package}}

# Install a new frontend dependency
add-dep-frontend package:
    docker compose exec frontend npm install {{package}}
