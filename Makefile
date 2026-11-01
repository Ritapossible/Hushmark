.PHONY: install lint test verify fmt

install:
	uv sync --locked

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy

fmt:
	uv run ruff format .
	uv run ruff check --fix .

test:
	uv run pytest

# Offline: every fixture, no API key, no network.
verify:
	uv run pytest -m "not live"
