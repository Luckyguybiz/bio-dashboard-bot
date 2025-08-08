.PHONY: up down lint fmt test migrate

up:
	docker compose up -d

down:
	docker compose down -v

lint:
	pre-commit run --all-files --hook-stage=manual ruff

fmt:
	pre-commit run --all-files --hook-stage=manual black isort

test:
	pytest

migrate:
	alembic revision --autogenerate -m "$(m)"
