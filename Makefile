.PHONY: install import test bot health evaluate

install:
	uv sync --locked

import:
	PYTHONPATH=src uv run uzex import uzex_spot_data.zip

test:
	uv run ruff check src scripts tests
	uv run ruff format --check src scripts tests
	uv run pytest -q

bot:
	PYTHONPATH=src uv run uzex bot

health:
	PYTHONPATH=src uv run uzex health

evaluate:
	PYTHONPATH=src uv run uzex evaluate
