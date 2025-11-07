.PHONY: help setup install install-dev lint format test test-cov clean package
.DEFAULT_GOAL := help

# Colours for output
CYAN := \033[0;36m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
RESET := \033[0m

VENV := ../.venv
PYTHON := $(VENV)/bin/python
PYTEST := $(VENV)/bin/pytest
RUFF := $(VENV)/bin/ruff

help: ## Show this help message
	@echo "$(CYAN)mcp-server-core$(RESET) - Reusable MCP server platform components"
	@echo ""
	@echo "$(GREEN)Available targets:$(RESET)"
	@awk 'BEGIN {FS = ":.*##"; printf ""} /^[a-zA-Z_-]+:.*?##/ { printf "  $(CYAN)%-15s$(RESET) %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

setup: ## Create shared virtual environment (requires uv)
	@if ! command -v uv >/dev/null 2>&1; then \
		echo "$(RED)Error: uv is not installed$(RESET)"; \
		echo "$(YELLOW)Install with: curl -LsSf https://astral.sh/uv/install.sh | sh$(RESET)"; \
		exit 1; \
	fi
	@echo "$(GREEN)Creating shared virtual environment with uv...$(RESET)"
	@cd .. && uv venv .venv
	@echo "$(GREEN)✓ Virtual environment created$(RESET)"
	@echo "$(YELLOW)Activate with: source $(VENV)/bin/activate$(RESET)"

install: $(VENV) ## Install package and dependencies
	@echo "$(GREEN)Installing mcp-server-core...$(RESET)"
	@uv pip install -e .
	@echo "$(GREEN)✓ Package installed$(RESET)"

install-dev: $(VENV) ## Install package with development dependencies
	@echo "$(GREEN)Installing mcp-server-core with dev dependencies...$(RESET)"
	@uv pip install -e ".[dev]"
	@echo "$(GREEN)✓ Package and dev dependencies installed$(RESET)"

lint: $(VENV) ## Run linting checks
	@echo "$(GREEN)Running ruff linter...$(RESET)"
	@$(RUFF) check mcp_server_core tests
	@echo "$(GREEN)✓ Linting passed$(RESET)"

format: $(VENV) ## Format code with ruff
	@echo "$(GREEN)Formatting code with ruff...$(RESET)"
	@$(RUFF) format mcp_server_core tests
	@$(RUFF) check --fix mcp_server_core tests
	@echo "$(GREEN)✓ Code formatted$(RESET)"

test: $(VENV) ## Run tests without coverage
	@echo "$(GREEN)Running tests...$(RESET)"
	@$(PYTEST) --no-cov -v

test-cov: $(VENV) ## Run tests with coverage report
	@echo "$(GREEN)Running tests with coverage...$(RESET)"
	@$(PYTEST)
	@echo ""
	@echo "$(YELLOW)View HTML coverage report: open coverage/html/index.html$(RESET)"

clean: ## Remove build artifacts and caches
	@echo "$(GREEN)Cleaning up...$(RESET)"
	@rm -rf build/ dist/ *.egg-info coverage/ .coverage .pytest_cache
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@echo "$(GREEN)✓ Clean complete$(RESET)"

clean-all: clean ## Remove build artifacts, caches, and shared virtual environment
	@echo "$(GREEN)Removing shared virtual environment...$(RESET)"
	@rm -rf $(VENV)
	@echo "$(GREEN)✓ Full clean complete$(RESET)"

package: $(VENV) ## Build distribution packages
	@echo "$(GREEN)Building package...$(RESET)"
	@$(PYTHON) -m pip install --upgrade build
	@$(PYTHON) -m build
	@echo "$(GREEN)✓ Package built in dist/$(RESET)"

$(VENV):
	@echo "$(YELLOW)Virtual environment not found. Run 'make setup' first.$(RESET)"
	@exit 1
