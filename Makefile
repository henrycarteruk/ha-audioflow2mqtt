.DEFAULT_GOAL := help

# The uv project lives inside the add-on directory (HA add-on build context).
PROJECT_DIR := audioflow2mqtt

.PHONY: help install test run lock clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "} {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

install: ## Create the virtualenv and install all dependencies (incl. dev)
	cd $(PROJECT_DIR) && uv sync

test: ## Run the test suite
	cd $(PROJECT_DIR) && uv run pytest

run: ## Run the add-on locally (python -m audioflow2mqtt)
	cd $(PROJECT_DIR) && uv run python -m audioflow2mqtt

lock: ## Update the dependency lockfile
	cd $(PROJECT_DIR) && uv lock

clean: ## Remove the virtualenv and caches
	rm -rf $(PROJECT_DIR)/.venv $(PROJECT_DIR)/.pytest_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
