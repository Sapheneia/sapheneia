.PHONY: help up down reset test test-unit test-integration smoke fmt lint logs status

help:
	@echo "Sapheneia targets:"
	@echo "  make up              start the docker stack + migrations + skill symlinks"
	@echo "  make down            stop containers (preserve data)"
	@echo "  make reset           down + wipe .timescaledb-data/ + remove symlinks"
	@echo "  make test            run all tests"
	@echo "  make test-unit       run unit tests only (skip integration)"
	@echo "  make test-integration run integration tests only"
	@echo "  make smoke           up + run a single example simulation + down"
	@echo "  make fmt             format with black + ruff --fix"
	@echo "  make lint            ruff check + mypy"
	@echo "  make logs SERVICE=...  tail logs for one service (or all)"
	@echo "  make status          docker compose ps"

up:
	./setup.sh up

down:
	./setup.sh down

reset:
	./setup.sh reset

test:
	uv run pytest

test-unit:
	uv run pytest -m "not integration"

test-integration:
	uv run pytest -m integration

smoke:
	./setup.sh up
	uv run sapheneia simulate --strategy simulations/templates/spy_chronos_tiny.example.yaml || true
	./setup.sh down

fmt:
	uv run black .
	uv run ruff check --fix .

lint:
	uv run ruff check .
	uv run mypy --ignore-missing-imports forecast trading metrics data orchestrator sapheneia sapheneia_mcp shared || true

logs:
	./setup.sh logs $(SERVICE)

status:
	./setup.sh status
