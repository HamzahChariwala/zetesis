.PHONY: dev-db dev-server dev-web dev migrate test seed

dev-db:
	docker compose up -d db

dev-server:
	cd packages/server && uv run uvicorn zetesis_server.main:app --reload --port 8000

dev-web:
	cd packages/web && npm run dev

dev: dev-db
	$(MAKE) dev-server & $(MAKE) dev-web

migrate:
	cd packages/server && uv run alembic upgrade head

test:
	uv run pytest tests/ -v

seed:
	uv run python scripts/seed.py
