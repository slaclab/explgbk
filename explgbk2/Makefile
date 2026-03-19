.PHONY: test test-backend test-frontend test-backend-build test-frontend-build up up-build up-test-frontend generate-client

test: test-backend test-frontend

up:
	docker compose up -d --wait

up-build:
	docker compose up -d --wait --build

test: test-backend test-frontend

test-backend:
	cd backend && uv run pytest tests/ --cov=app --cov-report=term --cov-report=html

test-frontend: up-build
	docker compose run --rm playwright bunx playwright test --reporter=line

prek:
	uv run prek install
	uv run prek run -a

lint:
	uv run prek run -a --skip generate-frontend-sdk

generate-client:
	uv run prek run generate-frontend-sdk
