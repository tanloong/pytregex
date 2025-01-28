.PHONY: refresh clean build release install test coverage lint

refresh: lint clean build install

clean:
	rm -rf __pycache__
	rm -rf tests/__pycache__
	rm -rf build
	rm -rf dist
	rm -rf src/*.egg-info
	rm -rf htmlcov
	rm -rf coverage.xml
	rm -rf parser.out src/parser.out
	uv pip uninstall pytregex || true

build:
	make clean
	uv build

release:
	python -m twine upload dist/*

install:
	uv pip install .

test:
	python -m unittest

coverage:
	python -m coverage run -m unittest
	python -m coverage html

lint:
	@ruff format src/ tests/ --silent
	@ruff check src/ tests/ --fix --output-format pylint
	@mypy src/ --show-column-numbers --no-error-summary
