.PHONY: help docs-serve docs-build docs-clean sync test lint format clean

UV ?= uv

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

##@ Documentation

docs-serve: ## Serve docs locally with live reload (http://127.0.0.1:8000)
	$(UV) run --group docs mkdocs serve

docs-build: ## Build static site into site/
	$(UV) run --group docs mkdocs build --strict

docs-clean: ## Remove built site
	rm -rf site/

##@ Environment

sync: ## Sync all dependencies (core + dev + docs)
	$(UV) sync --all-groups

##@ Quality (placeholder — no source code yet)

test: ## Run tests
	$(UV) run pytest

lint: ## Run linters
	$(UV) run flake8 src tests || true
	$(UV) run mypy src || true

format: ## Format source code
	$(UV) run black src tests

##@ Cleanup

clean: docs-clean ## Remove all build artifacts
	rm -rf __pycache__ *.egg-info .pytest_cache site
	find . -type d -name __pycache__ -exec rm -rf {} +
