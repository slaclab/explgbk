.PHONY: test test-backend test-frontend up generate-client prek lint

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
