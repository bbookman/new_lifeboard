.PHONY: help lint format type-check test test-quick clean install install-dev setup-pre-commit

help:				## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Development setup
install:			## Install production dependencies
	pip install -r requirements.txt

install-dev: install		## Install development dependencies
	pip install black ruff mypy pre-commit

setup-pre-commit:		## Setup pre-commit hooks
	pre-commit install

# Code quality
lint:				## Run all linting checks
	@echo "Running ruff..."
	ruff check .
	@echo "Running mypy..."
	mypy .

lint-fix:			## Run linting with auto-fixes
	@echo "Running ruff with fixes..."
	ruff check --fix .
	@echo "Running mypy..."
	mypy .

format:				## Format code with black
	@echo "Running black..."
	black .

format-check:			## Check code formatting without changes
	@echo "Checking black formatting..."
	black --check --diff .

type-check:			## Run type checking
	@echo "Running mypy..."
	mypy .

# Testing
test:				## Run all tests
	python3 -m pytest

test-quick:			## Run quick test subset
	python3 -m pytest -m "not slow" --maxfail=3

test-unit:			## Run unit tests only
	python3 -m pytest -m unit

test-integration:		## Run integration tests only
	python3 -m pytest -m integration

# Quality gates (for CI/pre-commit)
check-all: format-check lint type-check test-quick  ## Run all quality checks

# Cleanup
clean:				## Clean up temporary files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -name ".mypy_cache" -type d -exec rm -rf {} +
	find . -name ".pytest_cache" -type d -exec rm -rf {} +
	find . -name ".coverage" -delete

# Combined shortcuts for development workflow
dev-setup: install-dev setup-pre-commit  ## Complete development setup
	@echo "✅ Development environment ready!"

dev-check: format lint test-quick  ## Format, lint and test quickly
	@echo "✅ Code quality checks passed!"

# Pre-commit simulation (what pre-commit hooks will run)
pre-commit-sim:			## Simulate pre-commit hooks locally
	@echo "=== Simulating pre-commit hooks ==="
	black --check --diff .
	ruff check --no-fix .
	mypy --no-error-summary .
	@echo "✅ Pre-commit simulation passed!"