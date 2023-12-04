# Cbundle Makefile
#
SOURCES := tests/test_cb.py cbundle/cli.py

.PHONY: install test
install:
	poetry build
	pipx install ./ --force

test:
	poetry run pytest
