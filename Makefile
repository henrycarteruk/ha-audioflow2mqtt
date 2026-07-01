.DEFAULT_GOAL := help

# The uv project lives inside the add-on directory (HA add-on build context).
PROJECT_DIR := audioflow2mqtt
UV := uv --directory $(PROJECT_DIR)

.PHONY: help install test run lock bump clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "} {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

install: ## Create the virtualenv and install all dependencies (incl. dev)
	$(UV) sync

test: ## Run the test suite
	$(UV) run pytest

run: ## Run the add-on locally (python -m audioflow2mqtt)
	$(UV) run python -m audioflow2mqtt

lock: ## Update the dependency lockfile
	$(UV) lock --system-certs

bump: ## Set the release version in config.yaml + pyproject.toml and refresh the lock (VERSION=x.y.z)
	@test -n "$(VERSION)" || { echo "usage: make bump VERSION=x.y.z"; exit 1; }
	sed -i.bak -E 's/^version: .*/version: "$(VERSION)"/' $(PROJECT_DIR)/config.yaml && rm -f $(PROJECT_DIR)/config.yaml.bak
	sed -i.bak -E 's/^version = .*/version = "$(VERSION)"/' $(PROJECT_DIR)/pyproject.toml && rm -f $(PROJECT_DIR)/pyproject.toml.bak
	$(UV) lock --system-certs
	@echo "Bumped to $(VERSION) and refreshed uv.lock. Add a $(PROJECT_DIR)/CHANGELOG.md entry, then commit."

clean: ## Remove the virtualenv and caches
	rm -rf $(PROJECT_DIR)/.venv $(PROJECT_DIR)/.pytest_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
