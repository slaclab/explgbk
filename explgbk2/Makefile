.PHONY: test test-backend test-frontend up generate-client prek lint migration schema test-migrations

test: test-frontend test-backend

up:
	docker compose up -d --wait --build

test-backend:
	cd backend && uv run pytest tests/ --cov=app --cov-report=term --cov-report=html


test-frontend:
	docker compose up -d --wait backend
	cd frontend && bunx playwright test

prek:
	uv run prek install
	uv run prek run -a

lint:
	uv run prek run -a --skip generate-frontend-sdk

generate-client:
	uv run prek run generate-frontend-sdk

migration:  ## Generate an Alembic migration from SQLModel (uses testcontainers)
	cd backend/libs/pief-logdb && uv run python scripts/gen_migration.py
	$(MAKE) test-migrations

test-migrations:  ## Run Alembic migration tests (upgrade / drift-check / downgrade)
	cd backend && uv run pytest libs/pief-logdb/tests/test_migrations.py -v

# Install Node deps only when the lockfile changes (skipped if node_modules is current)
backend/libs/pief-logdb/scripts/dbml/node_modules: backend/libs/pief-logdb/scripts/dbml/package-lock.json
	npm ci --prefix backend/libs/pief-logdb/scripts/dbml
	@touch backend/libs/pief-logdb/scripts/dbml/node_modules

schema: backend/libs/pief-logdb/scripts/dbml/node_modules  ## Regenerate backend/libs/pief-logdb/artifacts/db.sql and backend/libs/pief-logdb/artifacts/db.dbml
	cd backend/libs/pief-logdb && uv run python scripts/gen_ddl.py
	cd backend/libs/pief-logdb/scripts/dbml && npx ts-node sql_to_dbml.ts
