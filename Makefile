.PHONY: install dev api web test lint qa train

install:
	./install.sh --local

api:
	. .venv/bin/activate && python -m uvicorn aurelia_api.main:app --port 8484

web:
	cd apps/web && npm run dev

dev: ## run API + web UI together
	$(MAKE) -j2 api web

test:
	./scripts/test_all.sh

lint:
	. .venv/bin/activate && ruff check services packages
	cd apps/web && npm run build

qa:
	./scripts/qa.sh

train:
	. .venv/bin/activate && aurelia train-mini-llm
