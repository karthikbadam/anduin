.PHONY: help up down logs ps register-schemas seed refresh-tle-fixture test clean fmt lint

COMPOSE := docker compose

help:
	@echo "Anduin — Satellite Tracking Platform"
	@echo ""
	@echo "Common targets:"
	@echo "  make up                   Start compose backbone + services"
	@echo "  make down                 Stop and remove containers (keep volumes)"
	@echo "  make logs                 Tail logs from all services"
	@echo "  make ps                   Show service status"
	@echo "  make register-schemas     Register Avro schemas with Schema Registry"
	@echo "  make seed                 Re-run Postgres seed SQL (dev data)"
	@echo "  make refresh-tle-fixture  Fetch Celestrak active.txt once (network required)"
	@echo "  make test                 Run pytest across Python services"
	@echo "  make clean                Remove containers AND volumes"

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=100

ps:
	$(COMPOSE) ps

register-schemas:
	./schemas/register.sh

seed:
	$(COMPOSE) exec -T postgres psql -U anduin -d anduin -f /docker-entrypoint-initdb.d/03-seed.sql

refresh-tle-fixture:
	$(COMPOSE) run --rm -T tle-producer python -m app.sources.celestrak --refresh-fixture

submit-flink-jobs:
	$(COMPOSE) exec -T flink-jm flink run -d -py /opt/flink/jobs/01_hot_sky_cells.py

test:
	@set -e; for svc in ingest-api query-api tle-producer position-persister; do \
		if [ -f $$svc/pyproject.toml ]; then \
			echo "=== $$svc ==="; \
			(cd $$svc && uv run pytest -q); \
		fi; \
	done

fmt:
	@for svc in ingest-api query-api tle-producer position-persister pass-worker dlq-consumer; do \
		[ -f $$svc/pyproject.toml ] && (cd $$svc && uv run ruff format .) || true; \
	done

lint:
	@for svc in ingest-api query-api tle-producer position-persister pass-worker dlq-consumer; do \
		[ -f $$svc/pyproject.toml ] && (cd $$svc && uv run ruff check . && uv run mypy .) || true; \
	done

clean:
	$(COMPOSE) down -v --remove-orphans
	@find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
	@find . -name .pytest_cache -type d -prune -exec rm -rf {} + 2>/dev/null || true
	@find . -name .mypy_cache -type d -prune -exec rm -rf {} + 2>/dev/null || true
	@find . -name .ruff_cache -type d -prune -exec rm -rf {} + 2>/dev/null || true
	@rm -rf frontend/node_modules frontend/dist
