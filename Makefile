# Color codes for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

PROTO_SOURCES = $(wildcard protos/*.proto)
PROTO_CLASSES = $(patsubst protos/%.proto,keynote_parser/generated/%_pb2.py,$(PROTO_SOURCES))

# Find protobuf include directory
PROTOBUF_INCLUDE := $(shell find /usr/local/Cellar/protobuf -name "descriptor.proto" 2>/dev/null | head -1 | xargs dirname | xargs dirname | xargs dirname 2>/dev/null || echo "")

.PHONY: help all clean install test build upload

.DEFAULT_GOAL := help

## help: Show this help message
help:
	@printf "\033[0;34mkeynote-parser Makefile targets:\033[0m\n\n"
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/^## //' | awk -F: '{printf "  \033[0;32m%-12s\033[0m %s\n", $$1, $$2}'
	@printf "\n"

## all: Generate protobuf files
all: $(PROTO_CLASSES) keynote_parser/generated/__init__.py
	@echo "$(GREEN)✓ Protobuf files generated successfully$(NC)"

## build: Build distribution packages
build: $(PROTO_CLASSES) keynote_parser/generated/__init__.py
	@echo "$(BLUE)Building distribution packages...$(NC)"
	@python3 -m build
	@echo "$(GREEN)✓ Build complete$(NC)"

## install: Install package in editable mode
install: $(PROTO_CLASSES) keynote_parser/generated/__init__.py
	@echo "$(BLUE)Installing package in editable mode...$(NC)"
	@python3 -m pip install -e .
	@echo "$(GREEN)✓ Installation complete$(NC)"

## upload: Upload package to PyPI
upload: build
	@echo "$(YELLOW)Uploading to PyPI...$(NC)"
	@python3 -m twine upload dist/*
	@echo "$(GREEN)✓ Upload complete$(NC)"

## clean: Remove generated files and build artifacts
clean:
	@echo "$(BLUE)Cleaning build artifacts...$(NC)"
	@rm -rf keynote_parser/generated
	@rm -rf keynote_parser.egg-info
	@rm -rf dist
	@rm -rf build
	@rm -rf *.pyc
	@find . -type d -name __pycache__ -exec rm -rf {} +
	@echo "$(GREEN)✓ Clean complete$(NC)"

## test: Run tests with coverage
test: all
	@echo "$(BLUE)Running tests...$(NC)"
	@python3 -m pytest . --cov=keynote_parser -W ignore::DeprecationWarning
	@echo "$(GREEN)✓ Tests complete$(NC)"

# Internal targets (not shown in help)
keynote_parser/generated:
	@mkdir -p keynote_parser/generated

keynote_parser/generated/%_pb2.py: protos/%.proto keynote_parser/generated
	@if [ -n "$(PROTOBUF_INCLUDE)" ]; then \
		protoc -I=$(PROTOBUF_INCLUDE) -I=protos --proto_path protos --python_out=keynote_parser/generated $< 2>&1 | grep -v "warning:" || true; \
	else \
		protoc -I=protos --proto_path protos --python_out=keynote_parser/generated $< 2>&1 | grep -v "warning:" || true; \
	fi

keynote_parser/generated/__init__.py: keynote_parser/generated $(PROTO_CLASSES)
	@touch $@
	@echo "$(BLUE)Fixing protobuf imports...$(NC)"
	@# Fix imports to be relative instead of absolute
	@# protoc generates: import TSPMessages_pb2 as TSPMessages__pb2
	@# We need: from . import TSPMessages_pb2 as TSPMessages__pb2
	@# This allows the generated files to work as a proper Python package
	@for file in keynote_parser/generated/*_pb2.py; do \
		sed -i.bak 's/^import \([A-Z].*_pb2\) as/from . import \1 as/g' $$file && rm $$file.bak; \
	done
	@echo "$(GREEN)✓ Protobuf imports fixed$(NC)"
