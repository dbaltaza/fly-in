MAP ?= maps/easy/01_linear_path.txt

install:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt

run:
	.venv/bin/python main.py $(MAP)

visual:
	.venv/bin/python main.py $(MAP) --pygame

debug:
	.venv/bin/python -m pdb main.py $(MAP)

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +
	find . -name "*.pyc" -delete

lint:
	.venv/bin/python -m flake8 .
	.venv/bin/python -m mypy . --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs

lint-strict:
	.venv/bin/python -m flake8 .
	.venv/bin/python -m mypy . --strict

.PHONY: install run debug clean lint lint-strict visual
