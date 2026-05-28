.PHONY: lint format package test

lint:
	ruff check slb
	black --check slb

format:
	ruff check --fix slb
	black slb

package:
	python scripts/package.py

test:
	pytest tests -q
