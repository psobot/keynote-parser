.PHONY: help install install-dev lint format type-check test pre-commit-install clean clean-all build
VENV := .venv
PYTHON := $(VENV)/bin/python
UV := uv

help:
	@echo "Available commands:"
	@echo "  make install          - Create venv and install package"
	@echo "  make install-dev      - Create venv and install with dev dependencies"
	@echo "  make lint             - Run ruff linter"
	@echo "  make format           - Format code with ruff"
	@echo "  make type-check       - Run pyright type checker"
	@echo "  make test             - Run tests with pytest"
	@echo "  make pre-commit-install - Install pre-commit hooks"
	@echo "  make clean            - Remove build artifacts"
	@echo "  make clean-all        - Remove build artifacts and virtualenv"
	@echo "  make build            - Build the package"

$(VENV):
	$(UV) venv $(VENV)

install: $(VENV)
	$(UV) pip install --python $(PYTHON) -e .

install-dev: $(VENV)
	$(UV) pip install --python $(PYTHON) -e ".[dev]"

lint: install-dev
	$(VENV)/bin/ruff check . --exclude keynote_parser/generated

format: install-dev
	$(VENV)/bin/ruff format . --exclude keynote_parser/generated

type-check: install-dev
	$(VENV)/bin/pyright keynote_parser --ignore keynote_parser/generated

test: install-dev
	$(VENV)/bin/pytest --cov=keynote_parser

pre-commit-install: install-dev
	$(VENV)/bin/pre-commit install

clean:
	rm -rf build/ dist/ *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete

clean-all: clean
	rm -rf $(VENV)

build: $(VENV)
	$(PYTHON) -m build

