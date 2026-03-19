.PHONY: test test-backend test-frontend up

test: test-backend test-frontend

up:
	docker compose up -d --wait --scale playwright=0

test-backend: up
	docker compose exec backend bash scripts/tests-start.sh

test-frontend: up
	docker compose run --rm playwright bunx playwright test
