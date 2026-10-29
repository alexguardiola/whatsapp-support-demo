SHELL := /bin/bash
COMPOSE := docker compose

.PHONY: env up bootstrap fake down clean test logs e2e

env:
	@scripts/gen-env.sh

up: env
	$(COMPOSE) up -d --build --wait postgres redis chatwoot-rails chatwoot-sidekiq demo
	$(COMPOSE) up -d --build bot
	@echo "Chatwoot: http://localhost:3010  ·  Demo page: http://localhost:8088"

bootstrap:
	python3 scripts/bootstrap.py
	$(COMPOSE) up -d --force-recreate bot

fake:
	BOT_FAKE_LLM=true $(COMPOSE) up -d --force-recreate bot

e2e:
	python3 scripts/e2e.py

test:
	cd bot && uv run pytest -q

logs:
	$(COMPOSE) logs -f --tail=50 bot chatwoot-rails

down:
	$(COMPOSE) down

clean:
	$(COMPOSE) down --volumes --rmi local
	rm -f .env demo/config.js
	@echo "Removed this demo's containers, volumes, image, .env and demo/config.js."
